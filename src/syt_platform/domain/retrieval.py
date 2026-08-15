"""真实检索执行器、逐查询审计记录与基准运行模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class RetrievalRunRequest(BaseModel):
    role: str = Field(default="researcher", pattern="^(researcher|planner|writer|reviewer)$")
    top_k: int = Field(default=5, ge=1, le=20)
    context_budget_tokens: int = Field(default=6000, ge=256, le=50000)
    seeds: list[int] = Field(default_factory=lambda: [13], min_length=1, max_length=5)
    include_ablations: bool = False
    evaluation_mode: str = Field(default="engineering", pattern="^(engineering|formal)$")

    @field_validator("seeds")
    @classmethod
    def unique_seeds(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class RetrievalQuerySummary(BaseModel):
    query_run_id: str
    query: str
    role: str
    seed: int = 13
    selected_ids: list[str]
    relevant_count: int
    recall_at_k: float
    reciprocal_rank_at_k: float
    provenance_coverage_at_k: float
    context_tokens: int
    latency_ms: float


class RetrievalSystemResult(BaseModel):
    system_id: str
    system_name: str
    implementation_level: str
    scorer_version: str
    query_results: list[RetrievalQuerySummary]
    mean_recall_at_k: float
    mean_mrr_at_k: float
    mean_provenance_coverage_at_k: float
    mean_context_tokens: float
    mean_latency_ms: float


class RetrievalEngineCheck(BaseModel):
    id: str
    name: str
    status: str
    detail: str


class RetrievalLogManifest(BaseModel):
    schema_version: str
    relative_path: str
    sha256: str
    record_count: int
    embedding_model: str
    embedding_dimension: int
    corpus_size: int


class RetrievalBenchmarkArtifact(BaseModel):
    systems: list[RetrievalSystemResult]
    engine_checks: list[RetrievalEngineCheck]
    log_manifest: RetrievalLogManifest
    validation_level: str
    benchmark_status: str
    efficacy_claim_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RetrievalBenchmarkRun(BaseModel):
    id: str
    project_id: str
    experiment_run_id: str
    method_run_id: str
    literature_run_id: str
    status: RunStatus
    embedding_model: str
    scorer_version: str
    request: RetrievalRunRequest
    execution_trace: list[ExecutionStep]
    result: RetrievalBenchmarkArtifact | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
