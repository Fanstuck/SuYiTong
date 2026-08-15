"""PACM-SW 选题拆解领域模型。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ContextItem(BaseModel):
    id: str
    source_type: str
    source_label: str
    content: str
    checksum: str


class ExecutionStep(BaseModel):
    step: str
    status: str
    detail: str


class TopicCandidate(BaseModel):
    title_cn: str
    title_en: str
    focus: str


class ProvenanceRecord(BaseModel):
    statement: str
    context_ids: list[str] = Field(default_factory=list)
    verification_status: str = "context_supported"


class TopicFramingResult(BaseModel):
    research_identity: str
    requirements_summary: str
    candidate_titles: list[TopicCandidate] = Field(min_length=1, max_length=5)
    problem_statement: str
    research_gap_hypotheses: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    proposed_contributions: list[str] = Field(default_factory=list)
    method_positioning: str
    core_modules: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    keywords_cn: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    literature_search_queries: list[str] = Field(default_factory=list)
    novelty_risks: list[str] = Field(default_factory=list)
    evidence_boundary: list[str] = Field(default_factory=list)
    provenance_map: list[ProvenanceRecord] = Field(default_factory=list)
    quality_gate_checklist: list[str] = Field(default_factory=list)


class TopicGateDecision(BaseModel):
    selected_candidate_index: int = Field(default=0, ge=0, le=4)
    review_notes: str = Field(default="", max_length=2000)


class TopicFramingRun(BaseModel):
    id: str
    project_id: str
    status: RunStatus
    model_name: str
    prompt_version: str
    input_contexts: list[ContextItem]
    execution_trace: list[ExecutionStep]
    result: TopicFramingResult | None = None
    decision: TopicGateDecision | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None


class TopicGateConfirmation(BaseModel):
    project: "ResearchProject"
    run: TopicFramingRun


from syt_platform.domain.project import ResearchProject  # noqa: E402

TopicGateConfirmation.model_rebuild()
