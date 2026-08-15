"""可追溯文献调研领域模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from syt_platform.domain.project import ResearchProject
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class PaperRecord(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    cited_by_count: int = 0
    source: str
    source_record_id: str
    matched_query: str
    relevance_score: float = 0.0


class EvidenceClaim(BaseModel):
    claim: str
    paper_ids: list[str] = Field(default_factory=list)
    verification_status: str = "evidence_supported"
    confidence: str = "medium"


class LiteratureTheme(BaseModel):
    name: str
    description: str
    paper_ids: list[str] = Field(default_factory=list)


class LiteratureSynthesis(BaseModel):
    review_scope: str
    executive_summary: str
    themes: list[LiteratureTheme] = Field(default_factory=list)
    key_findings: list[EvidenceClaim] = Field(default_factory=list)
    validated_gap_hypotheses: list[EvidenceClaim] = Field(default_factory=list)
    contradictions: list[EvidenceClaim] = Field(default_factory=list)
    related_work_draft: str
    method_implications: list[str] = Field(default_factory=list)
    search_limitations: list[str] = Field(default_factory=list)
    quality_gate_checklist: list[str] = Field(default_factory=list)

    @field_validator(
        "review_scope",
        "executive_summary",
        "related_work_draft",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        for key in ("description", "summary", "text", "content", "draft"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
        return "；".join(f"{key}: {item}" for key, item in value.items())

    @field_validator("method_implications", "search_limitations", mode="before")
    @classmethod
    def normalize_text_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("quality_gate_checklist", mode="before")
    @classmethod
    def normalize_quality_checklist(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [
                f"{key}: {'通过' if status is True else '未通过' if status is False else status}"
                for key, status in value.items()
            ]
        return value


class LiteratureGateDecision(BaseModel):
    review_notes: str = Field(default="", max_length=3000)


class LiteratureReviewRun(BaseModel):
    id: str
    project_id: str
    topic_run_id: str
    status: RunStatus
    model_name: str
    prompt_version: str
    queries: list[str]
    papers: list[PaperRecord]
    execution_trace: list[ExecutionStep]
    result: LiteratureSynthesis | None = None
    decision: LiteratureGateDecision | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None


class LiteratureGateConfirmation(BaseModel):
    project: ResearchProject
    run: LiteratureReviewRun
