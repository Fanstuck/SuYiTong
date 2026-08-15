"""B0 单智能体与 B1 多智能体对话生成基线执行器。"""

from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from uuid import uuid4

from pydantic import ValidationError

from syt_platform.domain.experiment import ExperimentRun, ExperimentTask
from syt_platform.domain.generation_benchmark import (
    GeneratedArtifact,
    GenerationBatchArtifact,
    GenerationBatchRequest,
    GenerationBatchRun,
    GenerationCellSummary,
    GenerationSystemSummary,
)
from syt_platform.domain.literature import LiteratureReviewRun
from syt_platform.domain.project import ResearchProject, ResearchStage
from syt_platform.domain.qrels import QrelsSet
from syt_platform.domain.retrieval import RetrievalLogManifest
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus
from syt_platform.repositories.generation_runs import GenerationRunRepository
from syt_platform.services.model_gateway import JiuwenModelGateway, ModelGatewayError
from syt_platform.services.retrieval_benchmark import JsonlAuditWriter


GENERATION_SCHEMA = "syt-generation-jsonl-v1"
GENERATION_RUNNER_VERSION = "b0-b1-generation-v1"


class GenerationBenchmarkError(RuntimeError):
    pass


class GenerationCellExecutionError(RuntimeError):
    """保留单个生成单元失败前已经实际发起的模型调用数。"""

    def __init__(self, message: str, model_calls: int) -> None:
        super().__init__(message)
        self.model_calls = model_calls


def _citation_ids(text: str, citations: list[str]) -> list[str]:
    found = re.findall(r"PAPER-\d{3}", text.upper())
    found.extend(item.upper() for item in citations if re.fullmatch(r"PAPER-\d{3}", item.upper()))
    return list(dict.fromkeys(found))


class GenerationBenchmarkService:
    def __init__(
        self,
        repository: GenerationRunRepository,
        model_gateway: JiuwenModelGateway,
        data_dir: Path,
    ) -> None:
        self.repository = repository
        self.model_gateway = model_gateway
        self.data_dir = data_dir

    @staticmethod
    def _static_context(literature: LiteratureReviewRun, budget_tokens: int) -> str:
        blocks = [
            f"[{paper.id}] {paper.title}\n{paper.abstract}\nDOI: {paper.doi}"
            for paper in sorted(literature.papers, key=lambda item: item.id)
        ]
        return "\n\n".join(blocks)[: budget_tokens * 4]

    @staticmethod
    def _artifact_prompt(task: ExperimentTask, seed: int, context: str) -> str:
        return json.dumps(
            {
                "task": task.model_dump(mode="json"),
                "seed_label": seed,
                "frozen_context": context,
                "output_contract": {
                    "final_text": "完成的学术写作产物，引用必须使用 [PAPER-###]",
                    "citations": ["PAPER-###"],
                    "decisions": ["本轮明确采用的写作或方法决定"],
                },
                "rules": [
                    "只能引用 frozen_context 中存在的 PAPER id",
                    "不得编造结果或实验数字",
                    "seed_label 只用于运行分组；供应商 seed 未验证",
                ],
            },
            ensure_ascii=False,
        )

    async def _run_b0(
        self, task: ExperimentTask, seed: int, context: str, writer: JsonlAuditWriter, run_id: str
    ) -> tuple[GeneratedArtifact, list[str], int]:
        generated = await self.model_gateway.generate_json(
            system_prompt=(
                "你是 B0 Single-Agent 基线。只进行一次生成，不使用外部检索、持久记忆或其他智能体。"
                "严格输出 JSON：final_text,citations,decisions。"
            ),
            user_prompt=self._artifact_prompt(task, seed, context),
            operation="b0_single_agent_generation",
            stage="experiment",
            max_tokens=2500,
        )
        artifact = GeneratedArtifact.model_validate(generated.data)
        writer.write({
            "schema_version": GENERATION_SCHEMA, "record_type": "agent_turn",
            "run_id": run_id, "system_id": "B0", "task_id": task.id, "seed": seed,
            "role": "single_agent", "turn": 1, "output": artifact.model_dump(mode="json"),
            "usage": generated.usage, "created_at": datetime.now(UTC).isoformat(),
        })
        return artifact, [], 1

    async def _run_b1(
        self, task: ExperimentTask, seed: int, context: str, writer: JsonlAuditWriter, run_id: str
    ) -> tuple[GeneratedArtifact, list[str], int]:
        base = self._artifact_prompt(task, seed, context)
        model_calls = 0
        try:
            model_calls += 1
            planner = await self.model_gateway.generate_json(
                system_prompt=(
                    "你是 B1 Planner。基于共享 transcript 制定写作计划。只输出 JSON："
                    "plan(list[str]),decisions(list[str]),evidence_ids(list[str])。"
                ),
                user_prompt=base,
                operation="b1_planner_generation",
                stage="experiment",
                max_tokens=1200,
            )
            plan = planner.data
            writer.write({
                "schema_version": GENERATION_SCHEMA, "record_type": "agent_turn",
                "run_id": run_id, "system_id": "B1", "task_id": task.id, "seed": seed,
                "role": "planner", "turn": 1, "output": plan, "usage": planner.usage,
                "created_at": datetime.now(UTC).isoformat(),
            })
            model_calls += 1
            drafted = await self.model_gateway.generate_json(
                system_prompt=(
                    "你是 B1 Writer。依据 Planner transcript 和固定上下文撰写。"
                    "只输出 JSON：final_text,citations,decisions。"
                ),
                user_prompt=json.dumps({"base": json.loads(base), "planner": plan}, ensure_ascii=False),
                operation="b1_writer_generation",
                stage="experiment",
                max_tokens=2500,
            )
            draft = GeneratedArtifact.model_validate(drafted.data)
            writer.write({
                "schema_version": GENERATION_SCHEMA, "record_type": "agent_turn",
                "run_id": run_id, "system_id": "B1", "task_id": task.id, "seed": seed,
                "role": "writer", "turn": 2, "output": draft.model_dump(mode="json"),
                "usage": drafted.usage, "created_at": datetime.now(UTC).isoformat(),
            })
            model_calls += 1
            reviewed = await self.model_gateway.generate_json(
                system_prompt=(
                    "你是 B1 Reviewer。核验引用与计划决定并直接返回修订后的最终产物。"
                    "不得添加上下文外来源。只输出 JSON：final_text,citations,decisions。"
                ),
                user_prompt=json.dumps(
                    {"task": task.model_dump(mode="json"), "planner": plan, "draft": draft.model_dump(mode="json"), "valid_ids": re.findall(r"PAPER-\d{3}", context)},
                    ensure_ascii=False,
                ),
                operation="b1_reviewer_generation",
                stage="experiment",
                max_tokens=2500,
            )
            final = GeneratedArtifact.model_validate(reviewed.data)
            writer.write({
                "schema_version": GENERATION_SCHEMA, "record_type": "agent_turn",
                "run_id": run_id, "system_id": "B1", "task_id": task.id, "seed": seed,
                "role": "reviewer", "turn": 3, "output": final.model_dump(mode="json"),
                "usage": reviewed.usage, "created_at": datetime.now(UTC).isoformat(),
            })
            decisions = plan.get("decisions", []) if isinstance(plan.get("decisions"), list) else []
            return final, [str(item) for item in decisions], model_calls
        except (ModelGatewayError, ValidationError, ValueError) as exc:
            raise GenerationCellExecutionError(str(exc), model_calls) from exc

    @staticmethod
    def _cell_summary(
        cell_id: str,
        system_id: str,
        task: ExperimentTask,
        seed: int,
        artifact: GeneratedArtifact,
        planned_decisions: list[str],
        valid_ids: set[str],
        model_calls: int,
    ) -> GenerationCellSummary:
        citations = _citation_ids(artifact.final_text, artifact.citations)
        valid = [item for item in citations if item in valid_ids]
        required = set(task.required_evidence_ids)
        retained = [item for item in planned_decisions if item and item in artifact.final_text]
        return GenerationCellSummary(
            cell_id=cell_id,
            system_id=system_id,
            task_id=task.id,
            seed=seed,
            status="completed",
            valid_citation_rate=round(len(valid) / len(citations), 4) if citations else 0.0,
            fabricated_reference_rate=round((len(citations) - len(valid)) / len(citations), 4) if citations else 0.0,
            required_evidence_coverage=round(len(required & set(valid)) / len(required), 4) if required else 0.0,
            decision_retention=(round(len(retained) / len(planned_decisions), 4) if planned_decisions else None),
            output_chars=len(artifact.final_text),
            model_calls=model_calls,
        )

    async def run(
        self,
        project: ResearchProject,
        experiment: ExperimentRun,
        literature: LiteratureReviewRun,
        qrels: QrelsSet | None,
        request: GenerationBatchRequest,
    ) -> GenerationBatchRun:
        if project.stage != ResearchStage.EXPERIMENT:
            raise GenerationBenchmarkError("项目尚未处于实验验证阶段")
        if experiment.status != RunStatus.COMPLETED or experiment.result is None:
            raise GenerationBenchmarkError("缺少已完成的实验协议")
        if request.mode == "formal" and (qrels is None or qrels.status != "frozen"):
            raise GenerationBenchmarkError("formal 批量运行前必须完成人工 qrels 并冻结")
        try:
            model_name = self.model_gateway.model_name
        except ModelGatewayError as exc:
            raise GenerationBenchmarkError(str(exc)) from exc
        trace = [ExecutionStep(
            step="freeze_generation_batch", status="completed",
            detail=f"protocol={experiment.id} literature={literature.id} qrels={qrels.id if qrels else 'none'}",
        ), ExecutionStep(
            step="execute_b0_b1", status="running",
            detail=f"seeds={request.seeds} task_limit={request.task_limit} mode={request.mode}",
        )]
        run = self.repository.create(
            project.id, experiment.id, qrels.id if qrels else None, model_name, request, trace
        )
        relative = Path("experiments") / project.id / run.id / "generation.jsonl"
        path = self.data_dir / relative
        writer = JsonlAuditWriter(path)
        cells: list[GenerationCellSummary] = []
        try:
            tasks = experiment.result.protocol.tasks[: request.task_limit]
            valid_ids = {paper.id for paper in literature.papers}
            context = self._static_context(literature, request.context_budget_tokens)
            writer.write({
                "schema_version": GENERATION_SCHEMA, "record_type": "run_header",
                "run_id": run.id, "project_id": project.id, "experiment_run_id": experiment.id,
                "qrels_set_id": qrels.id if qrels else None, "model": model_name,
                "runner_version": GENERATION_RUNNER_VERSION, "request": request.model_dump(mode="json"),
                "provider_seed_enforced": False, "created_at": datetime.now(UTC).isoformat(),
            })
            for seed in request.seeds:
                ordered_tasks = list(tasks)
                random.Random(seed).shuffle(ordered_tasks)
                for system_id in ("B0", "B1"):
                    for task in ordered_tasks:
                        cell_id = str(uuid4())
                        try:
                            if system_id == "B0":
                                artifact, decisions, calls = await self._run_b0(task, seed, context, writer, run.id)
                            else:
                                artifact, decisions, calls = await self._run_b1(task, seed, context, writer, run.id)
                            cell = self._cell_summary(
                                cell_id, system_id, task, seed, artifact, decisions, valid_ids, calls
                            )
                        except (GenerationCellExecutionError, ModelGatewayError, ValidationError, ValueError) as exc:
                            cell = GenerationCellSummary(
                                cell_id=cell_id, system_id=system_id, task_id=task.id, seed=seed,
                                status="failed", valid_citation_rate=0, fabricated_reference_rate=0,
                                required_evidence_coverage=0, output_chars=0,
                                model_calls=(exc.model_calls if isinstance(exc, GenerationCellExecutionError) else 1),
                                error=str(exc)[:1000],
                            )
                        cells.append(cell)
                        writer.write({
                            "schema_version": GENERATION_SCHEMA, "record_type": "cell_summary",
                            "run_id": run.id, **cell.model_dump(mode="json"),
                            "created_at": datetime.now(UTC).isoformat(),
                        })
            summaries: list[GenerationSystemSummary] = []
            for system_id, name in (("B0", "Single-Agent"), ("B1", "Multi-Agent Chat")):
                relevant = [cell for cell in cells if cell.system_id == system_id]
                completed = [cell for cell in relevant if cell.status == "completed"]
                summaries.append(GenerationSystemSummary(
                    system_id=system_id, system_name=name, cells=len(relevant),
                    completed_cells=len(completed), failed_cells=len(relevant) - len(completed),
                    mean_valid_citation_rate=round(mean(item.valid_citation_rate for item in completed), 4) if completed else 0,
                    mean_fabricated_reference_rate=round(mean(item.fabricated_reference_rate for item in completed), 4) if completed else 0,
                    mean_required_evidence_coverage=round(mean(item.required_evidence_coverage for item in completed), 4) if completed else 0,
                ))
            writer.write({
                "schema_version": GENERATION_SCHEMA, "record_type": "run_footer",
                "run_id": run.id, "status": "completed", "systems": [item.model_dump(mode="json") for item in summaries],
                "completed_at": datetime.now(UTC).isoformat(),
            })
            writer.close()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = RetrievalLogManifest(
                schema_version=GENERATION_SCHEMA, relative_path=relative.as_posix(),
                sha256=digest, record_count=writer.record_count,
                embedding_model=model_name, embedding_dimension=0, corpus_size=len(literature.papers),
            )
            trace[1] = ExecutionStep(
                step="execute_b0_b1", status="completed",
                detail=f"cells={len(cells)} completed={sum(item.status == 'completed' for item in cells)} failed={sum(item.status == 'failed' for item in cells)}",
            )
            trace.append(ExecutionStep(
                step="seal_generation_jsonl", status="completed",
                detail=f"records={writer.record_count} sha256={digest}",
            ))
            completed_count = sum(item.status == "completed" for item in cells)
            failed_count = len(cells) - completed_count
            formal_ready = request.mode == "formal" and qrels is not None and qrels.status == "frozen"
            benchmark_status = (
                "generation_batch_executed_all_cells_failed"
                if completed_count == 0
                else "b0_b1_batch_completed_qrels_frozen"
                if formal_ready
                else "engineering_batch_qrels_not_frozen"
            )
            blockers = [
                "模型供应商 seed 参数未验证；当前 seed 控制任务顺序与运行标签",
                "尚需将 B2/B3/Ours 生成系统纳入同一任务矩阵并完成人工写作质量评审",
            ]
            if failed_count:
                blockers.insert(0, f"{failed_count} 个生成实验单元失败；必须检查 JSONL 并复跑，不得丢弃")
            artifact = GenerationBatchArtifact(
                systems=summaries, cells=cells, log_manifest=manifest,
                validation_level="b0_b1_generation_engineering_or_formal_input",
                benchmark_status=benchmark_status,
                provider_seed_enforced=False, efficacy_claim_allowed=False,
                blockers=blockers,
            )
            return self.repository.complete(run.id, artifact, trace)
        except (GenerationBenchmarkError, OSError, ValueError) as exc:
            writer.close()
            trace[-1] = trace[-1].model_copy(update={"status": "failed", "detail": str(exc)[:300]})
            self.repository.fail(run.id, str(exc), trace)
            raise GenerationBenchmarkError(str(exc)) from exc
