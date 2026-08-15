"""PACM-SW 实验协议、预检与 pilot 结果模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from syt_platform.domain.project import ResearchProject
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


def _to_text(value: object) -> str:
    if isinstance(value, dict):
        return " · ".join(str(item) for item in value.values())
    return str(value)


class ExperimentSystemConfig(BaseModel):
    id: str
    name: str
    description: str
    memory_strategy: str
    retrieval_strategy: str
    provenance_enforced: bool = False
    role_aware: bool = False
    graph_enabled: bool = False
    conflict_detection: bool = False
    context_budget_tokens: int = Field(default=6000, ge=256, le=200000)


class ExperimentTask(BaseModel):
    id: str
    name: str
    task_type: str
    input_contract: str
    expected_artifact: str
    success_criteria: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("success_criteria", mode="before")
    @classmethod
    def normalize_criteria(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value


class MetricDefinition(BaseModel):
    name: str
    formula_or_procedure: str
    direction: str
    deterministic: bool
    required_inputs: list[str] = Field(default_factory=list)


class ExperimentProtocol(BaseModel):
    objective: str
    validation_scope: str
    systems: list[ExperimentSystemConfig] = Field(default_factory=list)
    tasks: list[ExperimentTask] = Field(default_factory=list)
    metrics: list[MetricDefinition] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    fairness_controls: list[str] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=lambda: [13, 37, 73])
    repetitions: int = Field(default=3, ge=1, le=20)
    statistics_plan: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    resource_budget: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    reproducibility_manifest: list[str] = Field(default_factory=list)
    quality_gate_checklist: list[str] = Field(default_factory=list)

    @field_validator(
        "ablations",
        "fairness_controls",
        "statistics_plan",
        "execution_order",
        "resource_budget",
        "stop_conditions",
        "reproducibility_manifest",
        "quality_gate_checklist",
        mode="before",
    )
    @classmethod
    def normalize_text_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [f"{key}: {_to_text(item)}" for key, item in value.items()]
        if isinstance(value, list):
            return [_to_text(item) for item in value]
        return value


class PreflightCheck(BaseModel):
    id: str
    name: str
    status: str
    detail: str


class PilotQueryResult(BaseModel):
    query: str
    relevant_count: int
    retrieved_ids: list[str]
    recall_at_5: float
    reciprocal_rank_at_5: float
    provenance_coverage_at_5: float
    token_proxy: int


class RetrievalPilotResult(BaseModel):
    system_id: str
    system_name: str
    implementation_level: str
    query_results: list[PilotQueryResult]
    mean_recall_at_5: float
    mean_mrr_at_5: float
    mean_provenance_coverage_at_5: float
    mean_token_proxy: float


class ExperimentArtifact(BaseModel):
    protocol: ExperimentProtocol
    preflight_checks: list[PreflightCheck]
    pilot_results: list[RetrievalPilotResult]
    validation_level: str
    benchmark_status: str
    efficacy_claim_allowed: bool
    blockers: list[str] = Field(default_factory=list)
    pilot_limitations: list[str] = Field(default_factory=list)


class ExperimentGateDecision(BaseModel):
    review_notes: str = Field(default="", max_length=3000)


class ExperimentRun(BaseModel):
    id: str
    project_id: str
    method_run_id: str
    literature_run_id: str
    status: RunStatus
    model_name: str
    prompt_version: str
    execution_trace: list[ExecutionStep]
    result: ExperimentArtifact | None = None
    decision: ExperimentGateDecision | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None


class ExperimentGateConfirmation(BaseModel):
    project: ResearchProject
    run: ExperimentRun
