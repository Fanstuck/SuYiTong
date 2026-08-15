"""PACM-SW 方法设计领域模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from syt_platform.domain.project import ResearchProject
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


def _mapping_to_text(value: dict[object, object]) -> str:
    preferred = []
    for key in ("id", "name", "description", "change", "purpose", "falsification_condition"):
        item = value.get(key)
        if item not in (None, ""):
            preferred.append(str(item))
    if preferred:
        return " · ".join(preferred)
    return "；".join(f"{key}: {item}" for key, item in value.items())


class MethodComponent(BaseModel):
    id: str
    name: str
    purpose: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    algorithm_steps: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class MemoryLayer(BaseModel):
    name: str
    content_types: list[str] = Field(default_factory=list)
    write_policy: str
    retrieval_role: str
    provenance_required: bool = True


class ProvenanceContract(BaseModel):
    entities: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)


class RetrievalScoreTerm(BaseModel):
    symbol: str
    name: str
    definition: str
    optimization_note: str = ""


class RetrievalObjective(BaseModel):
    formula: str
    terms: list[RetrievalScoreTerm] = Field(default_factory=list)
    candidate_generation: list[str] = Field(default_factory=list)
    budget_policy: str
    tie_break_policy: str = ""

    @field_validator("candidate_generation", mode="before")
    @classmethod
    def normalize_candidate_generation(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value


class ExperimentDesign(BaseModel):
    id: str
    research_question: str
    falsifiable_hypothesis: str
    baselines: list[str] = Field(default_factory=list)
    primary_metrics: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    falsification_condition: str


class EvidenceDesignLink(BaseModel):
    design_claim: str
    paper_ids: list[str] = Field(default_factory=list)
    rationale: str
    confidence: str = "medium"


class MethodDesignArtifact(BaseModel):
    method_name: str
    method_summary: str
    problem_formulation: str
    novelty_boundary: str
    components: list[MethodComponent] = Field(default_factory=list)
    memory_layers: list[MemoryLayer] = Field(default_factory=list)
    provenance_contract: ProvenanceContract
    retrieval_objective: RetrievalObjective
    context_assembly_protocol: list[str] = Field(default_factory=list)
    multi_agent_protocol: list[str] = Field(default_factory=list)
    experiment_designs: list[ExperimentDesign] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    implementation_contracts: list[str] = Field(default_factory=list)
    evidence_design_links: list[EvidenceDesignLink] = Field(default_factory=list)
    risks_and_limitations: list[str] = Field(default_factory=list)
    quality_gate_checklist: list[str] = Field(default_factory=list)

    @field_validator(
        "context_assembly_protocol",
        "multi_agent_protocol",
        "ablations",
        "implementation_contracts",
        "risks_and_limitations",
        "quality_gate_checklist",
        mode="before",
    )
    @classmethod
    def normalize_text_lists(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [_mapping_to_text(value)]
        if isinstance(value, list):
            return [
                _mapping_to_text(item) if isinstance(item, dict) else str(item)
                for item in value
            ]
        return value

    @field_validator(
        "method_summary",
        "problem_formulation",
        "novelty_boundary",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        for key in ("description", "summary", "text", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
        return "；".join(f"{key}: {item}" for key, item in value.items())


class MethodGateDecision(BaseModel):
    review_notes: str = Field(default="", max_length=3000)


class MethodDesignRun(BaseModel):
    id: str
    project_id: str
    literature_run_id: str
    status: RunStatus
    model_name: str
    prompt_version: str
    inherited_paper_ids: list[str]
    execution_trace: list[ExecutionStep]
    result: MethodDesignArtifact | None = None
    decision: MethodGateDecision | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    confirmed_at: datetime | None = None


class MethodGateConfirmation(BaseModel):
    project: ResearchProject
    run: MethodDesignRun
