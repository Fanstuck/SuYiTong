"""实验协议生成、确定性预检与检索 harness smoke test。"""

from __future__ import annotations

import json
import math
import re
from statistics import mean

from pydantic import ValidationError

from syt_platform.domain.experiment import (
    ExperimentArtifact,
    ExperimentProtocol,
    ExperimentRun,
    ExperimentSystemConfig,
    ExperimentTask,
    MetricDefinition,
    PilotQueryResult,
    PreflightCheck,
    RetrievalPilotResult,
)
from syt_platform.domain.literature import LiteratureReviewRun, PaperRecord
from syt_platform.domain.method_design import MethodDesignRun
from syt_platform.domain.project import ResearchProject, ResearchStage
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus
from syt_platform.repositories.experiment_runs import ExperimentRunRepository
from syt_platform.services.model_gateway import JiuwenModelGateway, ModelGatewayError


PROMPT_VERSION = "pacm-sw-experiment-protocol-v1"
REQUIRED_SYSTEMS = ("B0", "B1", "B2", "B3", "Ours")


class ExperimentError(RuntimeError):
    pass


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9-]{2,}", value.lower())
        if token not in {"the", "for", "and", "with", "from", "based", "aware"}
    }


def _provenance_completeness(paper: PaperRecord) -> float:
    fields = (paper.doi, paper.url, paper.abstract, paper.source_record_id, paper.source)
    return sum(bool(item) for item in fields) / len(fields)


class ExperimentService:
    def __init__(
        self,
        repository: ExperimentRunRepository,
        model_gateway: JiuwenModelGateway,
    ) -> None:
        self.repository = repository
        self.model_gateway = model_gateway

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 PACM-SW 实验方法学智能体。只能设计实验协议，不得生成或猜测实验结果。"
            "必须固定 B0 Single-Agent、B1 Multi-Agent Chat、B2 Flat Vector RAG、"
            "B3 Hybrid Retrieval、Ours PACM-SW 五个系统，使用相同基础模型、任务、文献集合、"
            "输出长度和预算规则。任务必须可执行，指标必须说明计算过程和所需输入。"
            "统计方案在看到结果前定义；保留负面、不显著和失败运行。"
            "只输出紧凑 JSON，不要 Markdown 或推理过程。顶层字段必须为 objective, "
            "validation_scope, systems, tasks, metrics, ablations, fairness_controls, seeds, "
            "repetitions, statistics_plan, execution_order, resource_budget, stop_conditions, "
            "reproducibility_manifest, quality_gate_checklist。systems 每项字段为 id,name,"
            "description,memory_strategy,retrieval_strategy,provenance_enforced,role_aware,"
            "graph_enabled,conflict_detection,context_budget_tokens；tasks 每项字段为 id,name,"
            "task_type,input_contract,expected_artifact,success_criteria,required_evidence_ids；"
            "metrics 每项字段为 name,formula_or_procedure,direction,deterministic,required_inputs。"
            "至少 4 个任务、6 个消融、3 个随机种子；不要填写任何观测数值。"
        )

    @staticmethod
    def _user_prompt(
        project: ResearchProject,
        method: MethodDesignRun,
        literature: LiteratureReviewRun,
    ) -> str:
        method_result = method.result
        assert method_result is not None
        payload = {
            "project": {
                "title": project.title,
                "method_run_id": method.id,
                "literature_run_id": literature.id,
            },
            "method_summary": method_result.method_summary,
            "method_components": [
                {"id": item.id, "name": item.name, "purpose": item.purpose}
                for item in method_result.components
            ],
            "retrieval_formula": method_result.retrieval_objective.formula,
            "provenance_invariants": method_result.provenance_contract.invariants,
            "approved_experiment_designs": [
                item.model_dump(mode="json") for item in method_result.experiment_designs
            ],
            "approved_ablations": method_result.ablations,
            "available_queries": literature.queries,
            "available_paper_ids": [paper.id for paper in literature.papers],
            "constraints": [
                "首轮正式任务集建议 4-6 个，技术验证集与冻结测试集分离",
                "种子默认 13,37,73，每配置每任务至少 3 次",
                "主表必须从原始 JSONL 运行记录重建",
                "当前只允许生成协议，结果由执行器产生",
                "Stanford Agentic Reviewer 仅作外部 manuscript-only 辅助评测",
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _default_system(system_id: str) -> ExperimentSystemConfig:
        defaults = {
            "B0": ("Single-Agent", "仅会话上下文", "none", False, False, False, False),
            "B1": ("Multi-Agent Chat", "共享对话历史", "none", False, False, False, False),
            "B2": ("Flat Vector RAG", "扁平外部记忆", "vector", False, False, False, False),
            "B3": ("Hybrid Retrieval", "扁平外部记忆", "BM25 + vector", False, False, False, False),
            "Ours": ("PACM-SW", "四层可溯源记忆", "hybrid + graph + provenance", True, True, True, True),
        }
        name, memory, retrieval, prov, role, graph, conflict = defaults[system_id]
        return ExperimentSystemConfig(
            id=system_id,
            name=name,
            description=f"{system_id} 对照配置",
            memory_strategy=memory,
            retrieval_strategy=retrieval,
            provenance_enforced=prov,
            role_aware=role,
            graph_enabled=graph,
            conflict_detection=conflict,
            context_budget_tokens=6000,
        )

    @classmethod
    def _normalize_protocol(
        cls,
        protocol: ExperimentProtocol,
        method: MethodDesignRun,
        literature: LiteratureReviewRun,
    ) -> ExperimentProtocol:
        known_ids = {paper.id for paper in literature.papers}
        by_id: dict[str, ExperimentSystemConfig] = {}
        for system in protocol.systems:
            normalized = "Ours" if system.id.lower() in {"ours", "pacm-sw"} else system.id.upper()
            if normalized in REQUIRED_SYSTEMS:
                by_id[normalized] = system.model_copy(update={"id": normalized})
        systems = [by_id.get(item, cls._default_system(item)) for item in REQUIRED_SYSTEMS]
        tasks = [
            task.model_copy(
                update={
                    "required_evidence_ids": list(
                        dict.fromkeys(
                            item for item in task.required_evidence_ids if item in known_ids
                        )
                    )
                }
            )
            for task in protocol.tasks
        ]
        while len(tasks) < 4:
            index = len(tasks)
            query = literature.queries[index % len(literature.queries)]
            tasks.append(
                ExperimentTask(
                    id=f"TASK-{index + 1:02d}",
                    name=f"证据约束任务 {index + 1}",
                    task_type="evidence_grounded_synthesis",
                    input_contract=query,
                    expected_artifact="带 PAPER id 的结构化 Claim 列表",
                    success_criteria=["引用有效", "Claim 可回指证据", "输出满足契约"],
                )
            )
        ablations = list(protocol.ablations)
        method_ablations = method.result.ablations if method.result else []
        for item in method_ablations:
            if len(ablations) >= 6:
                break
            if item not in ablations:
                ablations.append(item)
        required_metric_names = {
            "Reference Validity": ("verified references / all references", "higher", True),
            "Fabricated Reference Rate": ("invalid references / all references", "lower", True),
            "Claim Support Rate": ("supported core claims / all core claims", "higher", False),
            "Decision Retention": ("retained decisions / required decisions", "higher", True),
            "Context Token Cost": ("sum of model input tokens", "lower", True),
        }
        metrics = list(protocol.metrics)
        present = {item.name.lower() for item in metrics}
        for name, (formula, direction, deterministic) in required_metric_names.items():
            if name.lower() not in present:
                metrics.append(
                    MetricDefinition(
                        name=name,
                        formula_or_procedure=formula,
                        direction=direction,
                        deterministic=deterministic,
                        required_inputs=["raw run output", "evidence ledger"],
                    )
                )
        statistics_plan = protocol.statistics_plan or [
            "先报告每个配置×任务×种子的原始值、均值、标准差与 95% bootstrap 置信区间。",
            "Ours 与每个基线进行配对比较；正态性满足时使用配对 t 检验，否则使用 Wilcoxon 符号秩检验。",
            "多指标比较采用 Holm 校正，显著性阈值 alpha=0.05，并同时报告效应量。",
            "失败、超时和不显著结果全部保留；任何事后分析必须标注为 exploratory。",
        ]
        execution_order = protocol.execution_order or [
            "冻结语料、任务、gold qrels、提示词、模型版本、分词器与预算配置。",
            "实现并通过 B0、B1、B2、B3、Ours 五个系统的接口契约测试。",
            "按 seed 打乱配置顺序，执行 5 个系统×任务×3 个种子并写入逐运行 JSONL。",
            "执行 R1-R6 消融；任何异常重试都必须保留原运行记录和原因。",
            "从只读 JSONL 重建指标表、统计检验、误差分析与可视化。",
            "由人工审阅证据账本和失败样本，确认后才开放论文结果写作。",
        ]
        resource_budget = protocol.resource_budget or [
            "所有系统使用同一基础模型、temperature、最大输出长度和每轮上下文预算。",
            "每个系统×任务×种子单元最多 1 次正式运行；仅基础设施故障允许带原因重试。",
            "记录输入/输出 token、API 延迟、费用估算、检索候选数和最终上下文大小。",
        ]
        stop_conditions = protocol.stop_conditions or [
            "模型、语料或提示词版本发生漂移时停止批量运行并重新冻结清单。",
            "证据 ID 无法解析、原始日志无法落盘或预算不可比时立即阻断该运行。",
            "连续 3 次同类基础设施错误时暂停执行，不以补造数据替代失败样本。",
        ]
        reproducibility_manifest = protocol.reproducibility_manifest or [
            "代码提交、Python/依赖锁文件、操作系统与硬件摘要。",
            "脱敏模型配置、模型标识、采样参数、提示词版本与随机种子。",
            "冻结语料清单、DOI、OpenAlex/Crossref 来源 ID、gold qrels 与哈希。",
            "每次运行的 JSONL、检索轨迹、证据账本、错误日志与成本记录。",
            "指标重建脚本、统计脚本及生成表格/图形的命令。",
        ]
        quality_gate_checklist = protocol.quality_gate_checklist or [
            "五个正式系统与六个消融均有真实执行器，不使用 proxy 数值。",
            "所有主表数字均可从原始 JSONL 重建且能追溯到运行 ID。",
            "公平性约束、失败运行、重试与缺失值处理均已审计。",
            "统计方案在查看正式结果前冻结，报告效应量与校正后显著性。",
            "实验结论不超出任务集、数据集和实现层级的证据边界。",
        ]
        return protocol.model_copy(
            update={
                "systems": systems,
                "tasks": tasks,
                "metrics": metrics,
                "ablations": ablations[: max(6, len(ablations))],
                "seeds": list(dict.fromkeys(protocol.seeds or [13, 37, 73]))[:5],
                "repetitions": max(3, protocol.repetitions),
                "statistics_plan": statistics_plan,
                "execution_order": execution_order,
                "resource_budget": resource_budget,
                "stop_conditions": stop_conditions,
                "reproducibility_manifest": reproducibility_manifest,
                "quality_gate_checklist": quality_gate_checklist,
            }
        )

    @staticmethod
    def _preflight(
        protocol: ExperimentProtocol,
        method: MethodDesignRun,
        literature: LiteratureReviewRun,
    ) -> list[PreflightCheck]:
        system_ids = {item.id for item in protocol.systems}
        valid_dois = sum(bool(paper.doi) for paper in literature.papers)
        return [
            PreflightCheck(
                id="PF-01",
                name="上游冻结",
                status="pass",
                detail=f"方法运行 {method.id} 与文献运行 {literature.id} 均已确认",
            ),
            PreflightCheck(
                id="PF-02",
                name="系统配置覆盖",
                status="pass" if set(REQUIRED_SYSTEMS) <= system_ids else "block",
                detail=f"已定义 {', '.join(item.id for item in protocol.systems)}",
            ),
            PreflightCheck(
                id="PF-03",
                name="文献标识完整性",
                status="pass" if valid_dois == len(literature.papers) else "warn",
                detail=f"{valid_dois}/{len(literature.papers)} 篇记录包含 DOI",
            ),
            PreflightCheck(
                id="PF-04",
                name="重复与随机种子",
                status="pass" if protocol.repetitions >= 3 and len(protocol.seeds) >= 3 else "block",
                detail=f"重复 {protocol.repetitions} 次；种子 {protocol.seeds}",
            ),
            PreflightCheck(
                id="PF-05",
                name="真实检索执行器代码",
                status="pass",
                detail="B2 dense、B3 BM25+dense RRF 与 PACM-SW 四层检索器已实现；由独立 retrieval-run 执行和审计",
            ),
            PreflightCheck(
                id="PF-06",
                name="正式效果实验条件",
                status="block",
                detail="仍缺 B0/B1 生成任务、独立人工 qrels、六组消融与统计审计",
            ),
        ]

    @staticmethod
    def _rank_papers(
        papers: list[PaperRecord],
        query: str,
        system_id: str,
    ) -> list[PaperRecord]:
        query_tokens = _tokens(query)
        current_year = max((paper.year or 0 for paper in papers), default=2026)

        def score(paper: PaperRecord) -> float:
            text = f"{paper.title} {paper.abstract}".lower()
            overlap = sum(token in text for token in query_tokens) / max(1, len(query_tokens))
            provider_score = math.log1p(max(0.0, paper.relevance_score)) / 8
            if system_id == "B2-proxy":
                return provider_score
            lexical_hybrid = 0.65 * provider_score + 0.35 * overlap
            if system_id == "B3-proxy":
                return lexical_hybrid
            freshness = max(0.0, 1 - (current_year - (paper.year or current_year)) / 10)
            provenance = _provenance_completeness(paper)
            return 0.50 * lexical_hybrid + 0.35 * provenance + 0.15 * freshness

        return sorted(papers, key=lambda item: (score(item), item.id), reverse=True)

    @classmethod
    def _pilot(cls, literature: LiteratureReviewRun) -> list[RetrievalPilotResult]:
        configs = (
            ("B2-proxy", "Flat metadata-score proxy"),
            ("B3-proxy", "Hybrid metadata + lexical proxy"),
            ("Ours-proxy", "PACM-SW scoring proxy"),
        )
        results: list[RetrievalPilotResult] = []
        for system_id, name in configs:
            query_results: list[PilotQueryResult] = []
            for query in literature.queries:
                relevant = {
                    paper.id
                    for paper in literature.papers
                    if paper.matched_query.strip().lower() == query.strip().lower()
                }
                ranked = cls._rank_papers(literature.papers, query, system_id)[:5]
                retrieved_ids = [paper.id for paper in ranked]
                hits = [index for index, pid in enumerate(retrieved_ids, start=1) if pid in relevant]
                recall = len(hits) / len(relevant) if relevant else 0.0
                reciprocal_rank = 1 / hits[0] if hits else 0.0
                provenance = mean(_provenance_completeness(paper) for paper in ranked) if ranked else 0.0
                token_proxy = sum(len(paper.title) + len(paper.abstract) for paper in ranked) // 4
                query_results.append(
                    PilotQueryResult(
                        query=query,
                        relevant_count=len(relevant),
                        retrieved_ids=retrieved_ids,
                        recall_at_5=round(recall, 4),
                        reciprocal_rank_at_5=round(reciprocal_rank, 4),
                        provenance_coverage_at_5=round(provenance, 4),
                        token_proxy=token_proxy,
                    )
                )
            results.append(
                RetrievalPilotResult(
                    system_id=system_id,
                    system_name=name,
                    implementation_level="harness_proxy_not_paper_result",
                    query_results=query_results,
                    mean_recall_at_5=round(mean(item.recall_at_5 for item in query_results), 4),
                    mean_mrr_at_5=round(mean(item.reciprocal_rank_at_5 for item in query_results), 4),
                    mean_provenance_coverage_at_5=round(
                        mean(item.provenance_coverage_at_5 for item in query_results), 4
                    ),
                    mean_token_proxy=round(mean(item.token_proxy for item in query_results), 2),
                )
            )
        return results

    async def run(
        self,
        project: ResearchProject,
        method: MethodDesignRun,
        literature: LiteratureReviewRun,
    ) -> ExperimentRun:
        if project.stage != ResearchStage.EXPERIMENT:
            raise ExperimentError("项目尚未进入实验验证阶段")
        if method.status != RunStatus.COMPLETED or method.result is None or method.confirmed_at is None:
            raise ExperimentError("方法设计质量门尚未确认")
        if literature.status != RunStatus.COMPLETED or literature.result is None:
            raise ExperimentError("缺少已完成的文献调研产物")
        trace = [
            ExecutionStep(
                step="artifact_freeze",
                status="completed",
                detail=f"冻结方法运行 {method.id} 与文献运行 {literature.id}",
            ),
            ExecutionStep(
                step="protocol_generation",
                status="running",
                detail="正在生成不含实验结果的预注册协议",
            ),
        ]
        try:
            model_name = self.model_gateway.model_name
        except ModelGatewayError as exc:
            raise ExperimentError(str(exc)) from exc
        run = self.repository.create(
            project.id,
            method.id,
            literature.id,
            model_name,
            PROMPT_VERSION,
            trace,
        )
        try:
            generated = await self.model_gateway.generate_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(project, method, literature),
                operation="pacm_sw_experiment_protocol",
                stage="experiment",
                max_tokens=8000,
            )
            protocol = ExperimentProtocol.model_validate(generated.data)
            protocol = self._normalize_protocol(protocol, method, literature)
            trace[1] = ExecutionStep(
                step="protocol_generation",
                status="completed",
                detail=f"生成 {len(protocol.systems)} 个系统配置与 {len(protocol.tasks)} 个任务",
            )
            checks = self._preflight(protocol, method, literature)
            trace.append(
                ExecutionStep(
                    step="deterministic_preflight",
                    status="completed",
                    detail=(
                        f"预检 pass={sum(item.status == 'pass' for item in checks)}，"
                        f"block={sum(item.status == 'block' for item in checks)}"
                    ),
                )
            )
            pilot_results = self._pilot(literature)
            trace.append(
                ExecutionStep(
                    step="retrieval_harness_smoke",
                    status="completed",
                    detail=f"对 {len(literature.queries)} 条查询运行 3 个 proxy 配置",
                )
            )
            blockers = [item.detail for item in checks if item.status == "block"]
            artifact = ExperimentArtifact(
                protocol=protocol,
                preflight_checks=checks,
                pilot_results=pilot_results,
                validation_level="protocol_and_retrieval_harness_smoke",
                benchmark_status="formal_benchmark_pending",
                efficacy_claim_allowed=False,
                blockers=blockers,
                pilot_limitations=[
                    "协议运行内的 legacy pilot 使用元数据相关性分与词项重合；真实检索结果位于独立 retrieval-run。",
                    "Ours-proxy 仅加入题录级 provenance 完整度与时效信号，尚未实现图关系、角色匹配、冲突和冗余项。",
                    "相关集合由 matched_query 构造，仅用于检查 harness，不构成独立人工标注 qrels。",
                    "B0/B1 属于生成系统，不参与本次检索 smoke test。",
                    "所有 legacy pilot 数值禁止写入论文结果或用于方法有效性主张。",
                ],
            )
            return self.repository.complete(run.id, artifact, trace)
        except (ExperimentError, ModelGatewayError, ValidationError, ValueError) as exc:
            failed_index = next(
                (index for index, item in enumerate(trace) if item.status == "running"),
                len(trace) - 1,
            )
            trace[failed_index] = trace[failed_index].model_copy(
                update={"status": "failed", "detail": str(exc)[:300]}
            )
            self.repository.fail(run.id, str(exc), trace)
            raise ExperimentError(str(exc)) from exc
