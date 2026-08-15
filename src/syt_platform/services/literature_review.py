"""基于真实学术元数据的可追溯文献调研链路。"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from syt_platform.domain.literature import (
    EvidenceClaim,
    LiteratureReviewRun,
    LiteratureSynthesis,
    LiteratureTheme,
    PaperRecord,
)
from syt_platform.domain.project import ResearchProject
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus, TopicFramingRun
from syt_platform.repositories.literature_runs import LiteratureRunRepository
from syt_platform.services.academic_search import AcademicSearchError, AcademicSearchService
from syt_platform.services.model_gateway import JiuwenModelGateway, ModelGatewayError


PROMPT_VERSION = "pacm-sw-literature-review-v1"


class LiteratureReviewError(RuntimeError):
    pass


class LiteratureReviewService:
    def __init__(
        self,
        repository: LiteratureRunRepository,
        search_service: AcademicSearchService,
        model_gateway: JiuwenModelGateway,
    ) -> None:
        self.repository = repository
        self.search_service = search_service
        self.model_gateway = model_gateway

    @staticmethod
    def _queries(topic_run: TopicFramingRun) -> list[str]:
        if topic_run.result is None:
            return []
        queries = topic_run.result.literature_search_queries
        if not queries:
            queries = topic_run.result.keywords_en
        deduplicated: list[str] = []
        for query in queries:
            cleaned = query.strip()
            if cleaned and cleaned.lower() not in {item.lower() for item in deduplicated}:
                deduplicated.append(cleaned)
        return deduplicated[:6]

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 PACM-SW 可追溯文献调研智能体。只能使用用户消息中提供的 PAPER 记录，"
            "不得补充、猜测或捏造任何文献、作者、年份、DOI、结论或实验数据。"
            "每个主题、关键发现、研究空白和矛盾都必须通过 paper_ids 引用真实 PAPER id。"
            "若摘要缺失或证据不足，必须降低置信度并写入 search_limitations。"
            "related_work_draft 使用 [PAPER-001] 形式引用，不得生成作者年份之外的新引用。"
            "研究空白只能表述为本次检索范围内的证据结论，不能宣称穷尽全部文献。"
            "不要展示推理过程，只输出一个紧凑 JSON 对象，不要 Markdown。"
            "JSON 顶层字段必须为 review_scope, executive_summary, themes, key_findings, "
            "validated_gap_hypotheses, contradictions, related_work_draft, method_implications, "
            "search_limitations, quality_gate_checklist。"
            "themes 每项字段为 name, description, paper_ids；key_findings、"
            "validated_gap_hypotheses、contradictions 每项字段为 claim, paper_ids, "
            "verification_status, confidence。控制在 4 个主题、6 个发现、4 个缺口、"
            "3 个矛盾以内，Related Work 控制在 1000 字以内。"
        )

    @staticmethod
    def _user_prompt(
        project: ResearchProject,
        topic_run: TopicFramingRun,
        papers: list[PaperRecord],
        queries: list[str],
    ) -> str:
        selected_index = topic_run.decision.selected_candidate_index if topic_run.decision else 0
        selected = topic_run.result.candidate_titles[selected_index]  # type: ignore[union-attr]
        paper_payload = []
        for paper in papers[:18]:
            # Synthesis only needs compact evidence fields. Full records remain
            # persisted separately and are shown in the workbench.
            record = {
                "id": paper.id,
                "title": paper.title,
                "year": paper.year,
                "venue": paper.venue,
                "doi": paper.doi,
                "abstract": paper.abstract[:750],
                "matched_query": paper.matched_query,
            }
            paper_payload.append(record)
        payload = {
            "project_id": project.id,
            "selected_topic": selected.model_dump(mode="json"),
            "problem_statement": topic_run.result.problem_statement,  # type: ignore[union-attr]
            "gap_hypotheses_to_verify": topic_run.result.research_gap_hypotheses,  # type: ignore[union-attr]
            "research_questions": topic_run.result.research_questions,  # type: ignore[union-attr]
            "executed_queries": queries,
            "retrieved_papers": paper_payload,
            "rules": [
                "只引用 retrieved_papers 中的 PAPER id",
                "没有摘要的记录只能支持题录级判断",
                "区分证据支持、证据反驳和证据不足",
                "明确本轮检索数据库、查询数和文献数量限制",
                "输出可供下一阶段方法设计使用的约束与启示",
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_claims(
        claims: list[EvidenceClaim],
        known_ids: set[str],
    ) -> list[EvidenceClaim]:
        normalized: list[EvidenceClaim] = []
        for claim in claims:
            paper_ids = list(dict.fromkeys(item for item in claim.paper_ids if item in known_ids))
            status = claim.verification_status
            confidence = claim.confidence
            if not paper_ids:
                status = "insufficient_evidence"
                confidence = "low"
            normalized.append(
                claim.model_copy(
                    update={
                        "paper_ids": paper_ids,
                        "verification_status": status,
                        "confidence": confidence,
                    }
                )
            )
        return normalized

    @classmethod
    def _normalize_result(
        cls,
        result: LiteratureSynthesis,
        papers: list[PaperRecord],
    ) -> LiteratureSynthesis:
        known_ids = {paper.id for paper in papers}
        themes = [
            theme.model_copy(
                update={
                    "paper_ids": list(
                        dict.fromkeys(item for item in theme.paper_ids if item in known_ids)
                    )
                }
            )
            for theme in result.themes
        ]
        unknown_citation_pattern = re.compile(r"\[(PAPER-\d{3})\]")

        def keep_known_citation(match: re.Match[str]) -> str:
            return match.group(0) if match.group(1) in known_ids else "[未验证引用已移除]"

        related_work = unknown_citation_pattern.sub(
            keep_known_citation,
            result.related_work_draft,
        )
        return result.model_copy(
            update={
                "themes": themes,
                "key_findings": cls._normalize_claims(result.key_findings, known_ids),
                "validated_gap_hypotheses": cls._normalize_claims(
                    result.validated_gap_hypotheses, known_ids
                ),
                "contradictions": cls._normalize_claims(result.contradictions, known_ids),
                "related_work_draft": related_work,
            }
        )

    async def run(
        self,
        project: ResearchProject,
        topic_run: TopicFramingRun,
    ) -> LiteratureReviewRun:
        if (
            topic_run.status != RunStatus.COMPLETED
            or topic_run.result is None
            or topic_run.confirmed_at is None
        ):
            raise LiteratureReviewError("选题质量门尚未确认")
        queries = self._queries(topic_run)
        trace = [
            ExecutionStep(
                step="query_planning",
                status="completed",
                detail=f"从已确认选题产物读取 {len(queries)} 条检索式",
            ),
            ExecutionStep(
                step="metadata_retrieval",
                status="running",
                detail="正在检索 OpenAlex 与 Crossref 学术元数据",
            ),
        ]
        try:
            model_name = self.model_gateway.model_name
        except ModelGatewayError as exc:
            raise LiteratureReviewError(str(exc)) from exc
        run = self.repository.create(
            project.id,
            topic_run.id,
            model_name,
            PROMPT_VERSION,
            queries,
            trace,
        )
        papers: list[PaperRecord] = []
        try:
            papers = await self.search_service.search(queries)
            with_abstract = sum(bool(paper.abstract) for paper in papers)
            with_doi = sum(bool(paper.doi) for paper in papers)
            trace[1] = ExecutionStep(
                step="metadata_retrieval",
                status="completed",
                detail=(
                    f"双源检索去重后获得 {len(papers)} 篇记录；"
                    f"DOI={with_doi}，摘要={with_abstract}"
                ),
            )
            if len(papers) < 6:
                raise LiteratureReviewError("有效文献记录不足 6 篇，不能形成综述质量门")
            trace.append(
                ExecutionStep(
                    step="evidence_synthesis",
                    status="running",
                    detail="正在通过 JiuwenSwarm 生成受 PAPER id 约束的证据综述",
                )
            )
            generated = await self.model_gateway.generate_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(project, topic_run, papers, queries),
                operation="pacm_sw_literature_review",
                stage="literature_review",
                max_tokens=8000,
            )
            result = LiteratureSynthesis.model_validate(generated.data)
            result = self._normalize_result(result, papers)
            usage_total = generated.usage.get("total", {})
            trace[2] = ExecutionStep(
                step="evidence_synthesis",
                status="completed",
                detail=(
                    f"{generated.model_name} 已完成受约束综述；"
                    f"token={usage_total.get('total_tokens', 0)}"
                ),
            )
            trace.append(
                ExecutionStep(
                    step="citation_validation",
                    status="completed",
                    detail="所有证据映射已过滤为本次检索的 PAPER id",
                )
            )
            return self.repository.complete(run.id, papers, result, trace)
        except (
            AcademicSearchError,
            LiteratureReviewError,
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
            self.repository.fail(run.id, str(exc), papers, trace)
            raise LiteratureReviewError(str(exc)) from exc
