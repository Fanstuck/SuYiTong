"""由已确认文献证据生成 PACM-SW 方法设计。"""

from __future__ import annotations

import json

from pydantic import ValidationError

from syt_platform.domain.literature import LiteratureReviewRun
from syt_platform.domain.method_design import (
    EvidenceDesignLink,
    MethodDesignArtifact,
    MethodDesignRun,
)
from syt_platform.domain.project import ResearchProject, ResearchStage
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus
from syt_platform.repositories.method_runs import MethodRunRepository
from syt_platform.services.model_gateway import JiuwenModelGateway, ModelGatewayError


PROMPT_VERSION = "pacm-sw-method-design-v1"


class MethodDesignError(RuntimeError):
    pass


class MethodDesignService:
    def __init__(
        self,
        repository: MethodRunRepository,
        model_gateway: JiuwenModelGateway,
    ) -> None:
        self.repository = repository
        self.model_gateway = model_gateway

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 PACM-SW 科研方法设计智能体。任务是把已确认的文献证据转化为可实现、"
            "可证伪、可消融的方法设计，不是撰写宣传文案。只能引用用户消息中的 PAPER id。"
            "不得虚构论文结论、实验结果、数据集表现或统计显著性；权重只能定义调参原则，"
            "不能预设最优数值。H3 若被标记为 evidence insufficient，必须保留为待验证命题。"
            "方法必须明确区分：分层记忆、溯源契约、候选召回、组合排序、预算化上下文装配、"
            "多智能体交接和冲突处理。实验设计必须包含基线、公平控制、主指标和证伪条件。"
            "不要展示推理过程，只输出一个紧凑 JSON 对象，不要 Markdown。"
            "顶层字段必须为 method_name, method_summary, problem_formulation, novelty_boundary, "
            "components, memory_layers, provenance_contract, retrieval_objective, "
            "context_assembly_protocol, multi_agent_protocol, experiment_designs, ablations, "
            "implementation_contracts, evidence_design_links, risks_and_limitations, "
            "quality_gate_checklist。"
            "components 每项字段：id,name,purpose,inputs,outputs,algorithm_steps,evidence_ids；"
            "memory_layers 每项字段：name,content_types,write_policy,retrieval_role,provenance_required；"
            "provenance_contract 字段：entities,relations,required_fields,invariants；"
            "retrieval_objective 字段：formula,terms,candidate_generation,budget_policy,tie_break_policy，"
            "其中 terms 每项为 symbol,name,definition,optimization_note；"
            "experiment_designs 每项为 id,research_question,falsifiable_hypothesis,baselines,"
            "primary_metrics,controls,falsification_condition；evidence_design_links 每项为 "
            "design_claim,paper_ids,rationale,confidence。"
        )

    @staticmethod
    def _user_prompt(project: ResearchProject, literature: LiteratureReviewRun) -> str:
        result = literature.result
        assert result is not None
        payload = {
            "project": {
                "title": project.title,
                "research_direction": project.research_direction,
                "method_working_name": "PACM-SW",
            },
            "literature_scope": result.review_scope,
            "literature_summary": result.executive_summary,
            "themes": [item.model_dump(mode="json") for item in result.themes],
            "key_findings": [
                item.model_dump(mode="json") for item in result.key_findings
            ],
            "gap_hypotheses": [
                item.model_dump(mode="json")
                for item in result.validated_gap_hypotheses
            ],
            "method_implications": result.method_implications,
            "paper_catalog": [
                {
                    "id": paper.id,
                    "title": paper.title,
                    "year": paper.year,
                    "doi": paper.doi,
                }
                for paper in literature.papers[:24]
            ],
            "frozen_research_questions": [
                "RQ1: 可溯源上下文记忆是否降低虚假引用和无证据论点？",
                "RQ2: 角色感知上下文选择是否在更低 Token 成本下保持或提升质量？",
                "RQ3: Claim-Evidence-Experiment 关系是否改善跨 Agent 阶段一致性？",
                "RQ4: provenance、图关系、时间/版本与冲突检测分别贡献多少？",
            ],
            "required_baselines": [
                "B0 Single-Agent",
                "B1 Multi-Agent Chat",
                "B2 Flat Vector RAG",
                "B3 Hybrid Retrieval",
                "Ours PACM-SW",
            ],
            "required_metrics": [
                "Reference Validity",
                "Fabricated Reference Rate",
                "Claim Support Rate",
                "Decision Retention",
                "Experiment-Paper Consistency",
                "Context Token Cost",
            ],
            "hard_constraints": [
                "至少 5 个方法组件和 4 个记忆层级",
                "排序公式必须包含相关性、provenance、角色/任务、图连接、时效、冲突与冗余",
                "所有生成内容与实验输入必须通过 provenance contract",
                "至少 4 个可证伪实验设计和 6 个单变量消融",
                "同一基础模型、任务、文献集合和预算规则下公平比较",
                "不得预设 PACM-SW 优于基线",
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_result(
        result: MethodDesignArtifact,
        known_ids: set[str],
    ) -> MethodDesignArtifact:
        components = [
            item.model_copy(
                update={
                    "evidence_ids": list(
                        dict.fromkeys(pid for pid in item.evidence_ids if pid in known_ids)
                    )
                }
            )
            for item in result.components
        ]
        evidence_links: list[EvidenceDesignLink] = []
        for item in result.evidence_design_links:
            paper_ids = list(
                dict.fromkeys(pid for pid in item.paper_ids if pid in known_ids)
            )
            evidence_links.append(
                item.model_copy(
                    update={
                        "paper_ids": paper_ids,
                        "confidence": item.confidence if paper_ids else "low",
                    }
                )
            )
        risks = list(result.risks_and_limitations)
        h3_guard = "H3 仍为证据不足的待验证命题，不构成已确认的新颖性结论。"
        if not any("H3" in item for item in risks):
            risks.append(h3_guard)
        return result.model_copy(
            update={
                "method_name": "PACM-SW",
                "components": components,
                "evidence_design_links": evidence_links,
                "risks_and_limitations": risks,
            }
        )

    @staticmethod
    def _validate_minimums(result: MethodDesignArtifact) -> None:
        failures: list[str] = []
        if len(result.components) < 5:
            failures.append("方法组件少于 5 个")
        if len(result.memory_layers) < 4:
            failures.append("记忆层级少于 4 个")
        if len(result.experiment_designs) < 4:
            failures.append("可证伪实验设计少于 4 个")
        if len(result.ablations) < 6:
            failures.append("消融项少于 6 个")
        if not result.retrieval_objective.terms:
            failures.append("检索公式没有定义评分项")
        if failures:
            raise MethodDesignError("；".join(failures))

    async def run(
        self,
        project: ResearchProject,
        literature: LiteratureReviewRun,
    ) -> MethodDesignRun:
        if project.stage != ResearchStage.METHOD_DESIGN:
            raise MethodDesignError("项目尚未进入方法设计阶段")
        if (
            literature.status != RunStatus.COMPLETED
            or literature.result is None
            or literature.confirmed_at is None
        ):
            raise MethodDesignError("文献调研质量门尚未确认")
        inherited_ids = [paper.id for paper in literature.papers]
        trace = [
            ExecutionStep(
                step="evidence_inheritance",
                status="completed",
                detail=f"冻结文献运行 {literature.id}，继承 {len(inherited_ids)} 个 PAPER id",
            ),
            ExecutionStep(
                step="method_synthesis",
                status="running",
                detail="正在生成 PACM-SW 架构、检索目标与智能体协议",
            ),
        ]
        try:
            model_name = self.model_gateway.model_name
        except ModelGatewayError as exc:
            raise MethodDesignError(str(exc)) from exc
        run = self.repository.create(
            project.id,
            literature.id,
            model_name,
            PROMPT_VERSION,
            inherited_ids,
            trace,
        )
        try:
            generated = await self.model_gateway.generate_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(project, literature),
                operation="pacm_sw_method_design",
                stage="method_design",
                max_tokens=9000,
            )
            result = MethodDesignArtifact.model_validate(generated.data)
            result = self._normalize_result(result, set(inherited_ids))
            self._validate_minimums(result)
            usage_total = generated.usage.get("total", {})
            trace[1] = ExecutionStep(
                step="method_synthesis",
                status="completed",
                detail=(
                    f"{generated.model_name} 已生成 {len(result.components)} 个方法组件；"
                    f"token={usage_total.get('total_tokens', 0)}"
                ),
            )
            trace.append(
                ExecutionStep(
                    step="evidence_contract_validation",
                    status="completed",
                    detail="组件和设计主张中的证据编号已过滤为继承 PAPER 白名单",
                )
            )
            trace.append(
                ExecutionStep(
                    step="evaluation_freeze_draft",
                    status="completed",
                    detail=(
                        f"形成 {len(result.experiment_designs)} 个可证伪实验设计与 "
                        f"{len(result.ablations)} 个消融项"
                    ),
                )
            )
            return self.repository.complete(run.id, result, trace)
        except (
            MethodDesignError,
            ModelGatewayError,
            ValidationError,
            ValueError,
        ) as exc:
            failed_index = next(
                (index for index, item in enumerate(trace) if item.status == "running"),
                len(trace) - 1,
            )
            trace[failed_index] = trace[failed_index].model_copy(
                update={"status": "failed", "detail": str(exc)[:300]}
            )
            self.repository.fail(run.id, str(exc), trace)
            raise MethodDesignError(str(exc)) from exc
