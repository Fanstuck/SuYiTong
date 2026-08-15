"""B0/B1 生成基线批量运行模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from syt_platform.domain.retrieval import RetrievalLogManifest
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class GenerationBatchRequest(BaseModel):
    seeds: list[int] = Field(default_factory=lambda: [13, 37, 73], min_length=1, max_length=5)
    task_limit: int = Field(default=4, ge=1, le=6)
    context_budget_tokens: int = Field(default=6000, ge=512, le=50000)
    mode: str = Field(default="engineering", pattern="^(engineering|formal)$")

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class GeneratedArtifact(BaseModel):
    final_text: str
    citations: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)


class GenerationCellSummary(BaseModel):
    cell_id: str
    system_id: str
    task_id: str
    seed: int
    status: str
    valid_citation_rate: float
    fabricated_reference_rate: float
    required_evidence_coverage: float
    decision_retention: float | None = None
    output_chars: int
    model_calls: int
    error: str | None = None


class GenerationSystemSummary(BaseModel):
    system_id: str
    system_name: str
    cells: int
    completed_cells: int
    failed_cells: int
    mean_valid_citation_rate: float
    mean_fabricated_reference_rate: float
    mean_required_evidence_coverage: float


class GenerationBatchArtifact(BaseModel):
    systems: list[GenerationSystemSummary]
    cells: list[GenerationCellSummary]
    log_manifest: RetrievalLogManifest
    validation_level: str
    benchmark_status: str
    provider_seed_enforced: bool
    efficacy_claim_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)


class GenerationBatchRun(BaseModel):
    id: str
    project_id: str
    experiment_run_id: str
    qrels_set_id: str | None = None
    status: RunStatus
    model_name: str
    request: GenerationBatchRequest
    execution_trace: list[ExecutionStep]
    result: GenerationBatchArtifact | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

