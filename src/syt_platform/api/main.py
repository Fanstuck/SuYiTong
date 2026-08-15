"""速易通中台 API 入口。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from syt_platform.config import Settings
from syt_platform.domain.project import ProjectCreate, ResearchProject, StageTransition
from syt_platform.domain.literature import (
    LiteratureGateConfirmation,
    LiteratureGateDecision,
    LiteratureReviewRun,
)
from syt_platform.domain.method_design import (
    MethodDesignRun,
    MethodGateConfirmation,
    MethodGateDecision,
)
from syt_platform.domain.experiment import (
    ExperimentGateConfirmation,
    ExperimentGateDecision,
    ExperimentRun,
)
from syt_platform.domain.retrieval import RetrievalBenchmarkRun, RetrievalRunRequest
from syt_platform.domain.qrels import (
    QrelsCreateRequest,
    QrelsJudgmentBatch,
    QrelsSet,
)
from syt_platform.domain.generation_benchmark import GenerationBatchRequest, GenerationBatchRun
from syt_platform.domain.topic_framing import (
    RunStatus,
    TopicFramingRun,
    TopicGateConfirmation,
    TopicGateDecision,
)
from syt_platform.repositories.projects import (
    InvalidStageTransitionError,
    ProjectNotFoundError,
    ProjectRepository,
)
from syt_platform.repositories.literature_runs import LiteratureRunRepository
from syt_platform.repositories.method_runs import MethodRunRepository
from syt_platform.repositories.experiment_runs import ExperimentRunRepository
from syt_platform.repositories.retrieval_runs import RetrievalRunRepository
from syt_platform.repositories.qrels import QrelsRepository
from syt_platform.repositories.generation_runs import GenerationRunRepository
from syt_platform.repositories.topic_runs import TopicRunRepository
from syt_platform.services.academic_search import AcademicSearchService
from syt_platform.services.jiuwenswarm import JiuwenSwarmAdapter
from syt_platform.services.literature_review import (
    LiteratureReviewError,
    LiteratureReviewService,
)
from syt_platform.services.method_design import MethodDesignError, MethodDesignService
from syt_platform.services.experiment import ExperimentError, ExperimentService
from syt_platform.services.embedding import OpenAIEmbeddingGateway
from syt_platform.services.model_gateway import JiuwenModelGateway
from syt_platform.services.retrieval_benchmark import (
    EmbeddingProvider,
    RetrievalBenchmarkError,
    RetrievalBenchmarkService,
)
from syt_platform.services.qrels import QrelsError, QrelsService
from syt_platform.services.generation_benchmark import (
    GenerationBenchmarkError,
    GenerationBenchmarkService,
)
from syt_platform.services.topic_framing import TopicFramingError, TopicFramingService


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


class EnvironmentUpdate(BaseModel):
    api_base: str = Field(max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    model_name: str = Field(max_length=200)
    model_provider: str = Field(default="OpenAI", max_length=100)
    custom_headers: str = Field(default="", max_length=2000)
    embed_api_base: str = Field(default="", max_length=500)
    embed_api_key: str | None = Field(default=None, max_length=500)
    embed_model: str = Field(default="", max_length=200)
    jina_api_key: str | None = Field(default=None, max_length=500)
    serper_api_key: str | None = Field(default=None, max_length=500)
    perplexity_api_key: str | None = Field(default=None, max_length=500)
    openalex_api_key: str | None = Field(default=None, max_length=500)

    @field_validator("api_base", "embed_api_base")
    @classmethod
    def validate_optional_url(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned and not cleaned.startswith(("http://", "https://")):
            raise ValueError("地址必须以 http:// 或 https:// 开头")
        return cleaned

    @field_validator(
        "api_key",
        "model_name",
        "model_provider",
        "custom_headers",
        "embed_api_key",
        "embed_model",
        "jina_api_key",
        "serper_api_key",
        "perplexity_api_key",
        "openalex_api_key",
    )
    @classmethod
    def reject_multiline_values(cls, value: str | None) -> str | None:
        if value is not None and ("\n" in value or "\r" in value):
            raise ValueError("环境变量值不能包含换行符")
        return value


def create_app(
    settings: Settings | None = None,
    model_gateway: JiuwenModelGateway | None = None,
    academic_search: AcademicSearchService | None = None,
    embedding_gateway: EmbeddingProvider | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()
    repository = ProjectRepository(resolved.database_path)
    topic_runs = TopicRunRepository(resolved.database_path)
    literature_runs = LiteratureRunRepository(resolved.database_path)
    method_runs = MethodRunRepository(resolved.database_path)
    experiment_runs = ExperimentRunRepository(resolved.database_path)
    retrieval_runs = RetrievalRunRepository(resolved.database_path)
    qrels_sets = QrelsRepository(resolved.database_path)
    generation_runs = GenerationRunRepository(resolved.database_path)
    swarm = JiuwenSwarmAdapter(resolved.jiuwenswarm_data_dir)
    search_service = academic_search or AcademicSearchService(
        resolved.jiuwenswarm_data_dir / "config" / ".env"
    )
    topic_service = TopicFramingService(
        topic_runs,
        model_gateway or JiuwenModelGateway(resolved.jiuwenswarm_data_dir),
    )
    literature_service = LiteratureReviewService(
        literature_runs,
        search_service,
        model_gateway or JiuwenModelGateway(resolved.jiuwenswarm_data_dir),
    )
    method_service = MethodDesignService(
        method_runs,
        model_gateway or JiuwenModelGateway(resolved.jiuwenswarm_data_dir),
    )
    experiment_service = ExperimentService(
        experiment_runs,
        model_gateway or JiuwenModelGateway(resolved.jiuwenswarm_data_dir),
    )
    resolved_embedding_gateway = embedding_gateway or OpenAIEmbeddingGateway(
        resolved.jiuwenswarm_data_dir,
        resolved.data_dir / "embedding_cache.db",
    )
    retrieval_service = RetrievalBenchmarkService(
        retrieval_runs,
        resolved_embedding_gateway,
        resolved.data_dir,
    )
    qrels_service = QrelsService(qrels_sets, resolved.data_dir)
    generation_service = GenerationBenchmarkService(
        generation_runs,
        model_gateway or JiuwenModelGateway(resolved.jiuwenswarm_data_dir),
        resolved.data_dir,
    )

    application = FastAPI(
        title="速易通科研论文自动化中台",
        version="0.1.0",
        description="科研项目状态、证据、实验和论文工作流的权威业务层。",
    )

    if WEB_ROOT.exists():
        application.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

    @application.get("/", include_in_schema=False)
    def console() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @application.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "service": "suyitong-platform"}

    @application.get("/api/v1/system/capabilities")
    def capabilities() -> dict[str, object]:
        environment = swarm.model_configuration()
        return {
            "model_execution": "third_party_api",
            "local_model_required": False,
            "channels": ["web"],
            "research_modes": ["full", "semi"],
            "vertical_slices": [
                "intake_to_topic_framing",
                "literature_review_to_method_design",
                "method_design_to_experiment",
                "experiment_protocol_and_pilot",
                "real_b2_b3_pacm_retrieval_and_jsonl",
                "blind_human_qrels_and_ablation_batch",
                "b0_b1_generation_batch",
            ],
            "jiuwenswarm": asdict(swarm.status()),
            "academic_search": {
                "providers": ["OpenAlex", "Crossref"],
                "openalex_authenticated": environment.has_openalex_api_key,
                "crossref_authentication_required": False,
                "deduplication": ["DOI", "normalized_title"],
                "evidence_citation": "PAPER-id whitelist",
            },
            "embedding": {
                "configured": bool(
                    environment.embed_api_base
                    and environment.embed_model
                    and environment.has_embed_api_key
                ),
                "model": environment.embed_model,
                "engines": ["B2 Flat Vector", "B3 BM25+dense RRF", "PACM-SW"],
                "audit_log": "per-run JSONL + SHA-256",
            },
        }

    @application.get("/api/v1/system/environment")
    def environment() -> dict[str, object]:
        return asdict(swarm.model_configuration())

    @application.put("/api/v1/system/environment")
    def update_environment(request: EnvironmentUpdate) -> dict[str, object]:
        configuration = swarm.update_environment(
            {
                "API_BASE": request.api_base,
                "API_KEY": request.api_key,
                "MODEL_NAME": request.model_name.strip(),
                "MODEL_PROVIDER": request.model_provider.strip() or "OpenAI",
                "CUSTOM_HEADERS": request.custom_headers.strip(),
                "EMBED_API_BASE": request.embed_api_base,
                "EMBED_API_KEY": request.embed_api_key,
                "EMBED_MODEL": request.embed_model.strip(),
                "JINA_API_KEY": request.jina_api_key,
                "SERPER_API_KEY": request.serper_api_key,
                "PERPLEXITY_API_KEY": request.perplexity_api_key,
                "OPENALEX_API_KEY": request.openalex_api_key,
            }
        )
        return {
            **asdict(configuration),
            "message": "环境配置已保存；JiuwenSwarm 重启后将使用新配置",
        }

    @application.post("/api/v1/system/model/test")
    def test_model_connection() -> dict[str, object]:
        result = swarm.test_model_connection()
        if not result.ok:
            raise HTTPException(status_code=422, detail=asdict(result))
        return asdict(result)

    @application.post("/api/v1/system/openalex/test")
    async def test_openalex_connection() -> dict[str, object]:
        result = await search_service.test_openalex_connection()
        if not result.ok:
            raise HTTPException(status_code=422, detail=asdict(result))
        return asdict(result)

    @application.post("/api/v1/system/embedding/test")
    async def test_embedding_connection() -> dict[str, object]:
        result = await resolved_embedding_gateway.test_connection()
        if not result.ok:
            raise HTTPException(status_code=422, detail=asdict(result))
        return asdict(result)

    @application.post(
        "/api/v1/projects",
        response_model=ResearchProject,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(request: ProjectCreate) -> ResearchProject:
        return repository.create(request)

    @application.get("/api/v1/projects", response_model=list[ResearchProject])
    def list_projects() -> list[ResearchProject]:
        return repository.list()

    @application.get("/api/v1/projects/{project_id}", response_model=ResearchProject)
    def get_project(project_id: str) -> ResearchProject:
        try:
            return repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc

    @application.get(
        "/api/v1/projects/{project_id}/topic-framing/runs/latest",
        response_model=TopicFramingRun | None,
    )
    def latest_topic_framing_run(project_id: str) -> TopicFramingRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return topic_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/topic-framing/runs",
        response_model=TopicFramingRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_topic_framing(project_id: str) -> TopicFramingRun:
        try:
            project = repository.get(project_id)
            return await topic_service.run(project)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        except TopicFramingError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post(
        "/api/v1/projects/{project_id}/topic-framing/confirm",
        response_model=TopicGateConfirmation,
    )
    def confirm_topic_framing(
        project_id: str,
        request: TopicGateDecision,
    ) -> TopicGateConfirmation:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        latest = topic_runs.latest(project_id)
        if latest is None or latest.status != RunStatus.COMPLETED or latest.result is None:
            raise HTTPException(status_code=409, detail="尚无可确认的选题拆解产物")
        if request.selected_candidate_index >= len(latest.result.candidate_titles):
            raise HTTPException(status_code=422, detail="候选题目序号无效")
        confirmed_run = topic_runs.confirm(latest.id, request)
        project = repository.enter_literature_review_from_confirmed_topic(project_id)
        return TopicGateConfirmation(project=project, run=confirmed_run)

    @application.get(
        "/api/v1/projects/{project_id}/literature-review/runs/latest",
        response_model=LiteratureReviewRun | None,
    )
    def latest_literature_review_run(project_id: str) -> LiteratureReviewRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return literature_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/literature-review/runs",
        response_model=LiteratureReviewRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_literature_review(project_id: str) -> LiteratureReviewRun:
        try:
            project = repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        topic_run = topic_runs.latest(project_id)
        if topic_run is None:
            raise HTTPException(status_code=409, detail="尚无选题拆解产物")
        try:
            return await literature_service.run(project, topic_run)
        except LiteratureReviewError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post(
        "/api/v1/projects/{project_id}/literature-review/confirm",
        response_model=LiteratureGateConfirmation,
    )
    def confirm_literature_review(
        project_id: str,
        request: LiteratureGateDecision,
    ) -> LiteratureGateConfirmation:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        latest = literature_runs.latest(project_id)
        if latest is None or latest.status != RunStatus.COMPLETED or latest.result is None:
            raise HTTPException(status_code=409, detail="尚无可确认的文献调研产物")
        confirmed_run = literature_runs.confirm(latest.id, request)
        project = repository.enter_method_design_from_confirmed_literature(project_id)
        return LiteratureGateConfirmation(project=project, run=confirmed_run)

    @application.get(
        "/api/v1/projects/{project_id}/method-design/runs/latest",
        response_model=MethodDesignRun | None,
    )
    def latest_method_design_run(project_id: str) -> MethodDesignRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return method_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/method-design/runs",
        response_model=MethodDesignRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_method_design(project_id: str) -> MethodDesignRun:
        try:
            project = repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        literature_run = literature_runs.latest(project_id)
        if literature_run is None:
            raise HTTPException(status_code=409, detail="尚无文献调研产物")
        try:
            return await method_service.run(project, literature_run)
        except MethodDesignError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post(
        "/api/v1/projects/{project_id}/method-design/confirm",
        response_model=MethodGateConfirmation,
    )
    def confirm_method_design(
        project_id: str,
        request: MethodGateDecision,
    ) -> MethodGateConfirmation:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        latest = method_runs.latest(project_id)
        if latest is None or latest.status != RunStatus.COMPLETED or latest.result is None:
            raise HTTPException(status_code=409, detail="尚无可确认的方法设计产物")
        confirmed_run = method_runs.confirm(latest.id, request)
        project = repository.enter_experiment_from_confirmed_method(project_id)
        return MethodGateConfirmation(project=project, run=confirmed_run)

    @application.get(
        "/api/v1/projects/{project_id}/experiments/runs/latest",
        response_model=ExperimentRun | None,
    )
    def latest_experiment_run(project_id: str) -> ExperimentRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return experiment_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/experiments/runs",
        response_model=ExperimentRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_experiment(project_id: str) -> ExperimentRun:
        try:
            project = repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        method_run = method_runs.latest(project_id)
        literature_run = literature_runs.latest(project_id)
        if method_run is None or literature_run is None:
            raise HTTPException(status_code=409, detail="缺少方法或文献上游产物")
        try:
            return await experiment_service.run(project, method_run, literature_run)
        except ExperimentError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.post(
        "/api/v1/projects/{project_id}/experiments/confirm",
        response_model=ExperimentGateConfirmation,
    )
    def confirm_experiment(
        project_id: str,
        request: ExperimentGateDecision,
    ) -> ExperimentGateConfirmation:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        latest = experiment_runs.latest(project_id)
        if latest is None or latest.status != RunStatus.COMPLETED or latest.result is None:
            raise HTTPException(status_code=409, detail="尚无可确认的实验产物")
        if not latest.result.efficacy_claim_allowed:
            raise HTTPException(
                status_code=409,
                detail="当前仅完成协议与 harness smoke test；正式基线和消融尚未执行，不能进入论文写作",
            )
        confirmed_run = experiment_runs.confirm(latest.id, request)
        project = repository.enter_writing_from_confirmed_experiment(project_id)
        return ExperimentGateConfirmation(project=project, run=confirmed_run)

    @application.get(
        "/api/v1/projects/{project_id}/experiments/retrieval-runs/latest",
        response_model=RetrievalBenchmarkRun | None,
    )
    def latest_retrieval_run(project_id: str) -> RetrievalBenchmarkRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return retrieval_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/experiments/retrieval-runs",
        response_model=RetrievalBenchmarkRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_retrieval_benchmark(
        project_id: str,
        request: RetrievalRunRequest | None = None,
    ) -> RetrievalBenchmarkRun:
        try:
            project = repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        experiment_run = experiment_runs.latest(project_id)
        method_run = method_runs.latest(project_id)
        literature_run = literature_runs.latest(project_id)
        if experiment_run is None or method_run is None or literature_run is None:
            raise HTTPException(status_code=409, detail="缺少实验协议、方法或文献上游产物")
        try:
            qrels = qrels_sets.latest(project_id)
            return await retrieval_service.run(
                project,
                experiment_run,
                method_run,
                literature_run,
                request or RetrievalRunRequest(),
                qrels if qrels and qrels.status == "frozen" else None,
            )
        except RetrievalBenchmarkError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get(
        "/api/v1/projects/{project_id}/experiments/retrieval-runs/{run_id}/log",
        response_class=FileResponse,
    )
    def download_retrieval_log(project_id: str, run_id: str) -> FileResponse:
        try:
            repository.get(project_id)
            run = retrieval_runs.get(run_id)
        except (ProjectNotFoundError, LookupError) as exc:
            raise HTTPException(status_code=404, detail="检索运行不存在") from exc
        if run.project_id != project_id or run.result is None:
            raise HTTPException(status_code=404, detail="检索运行不存在或尚未完成")
        data_root = resolved.data_dir.resolve()
        log_path = (data_root / run.result.log_manifest.relative_path).resolve()
        if not log_path.is_relative_to(data_root) or not log_path.is_file():
            raise HTTPException(status_code=404, detail="JSONL 审计日志不存在")
        return FileResponse(
            log_path,
            media_type="application/x-ndjson",
            filename=f"retrieval-{run.id}.jsonl",
        )

    @application.get(
        "/api/v1/projects/{project_id}/experiments/qrels/latest",
        response_model=QrelsSet | None,
    )
    def latest_qrels(project_id: str) -> QrelsSet | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return qrels_sets.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/experiments/qrels",
        response_model=QrelsSet,
        status_code=status.HTTP_201_CREATED,
    )
    def create_qrels(project_id: str, request: QrelsCreateRequest) -> QrelsSet:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        retrieval = retrieval_runs.latest(project_id)
        literature = literature_runs.latest(project_id)
        if retrieval is None or literature is None:
            raise HTTPException(status_code=409, detail="请先完成真实检索运行")
        try:
            return qrels_service.create_pool(project_id, literature, retrieval, request)
        except QrelsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.put(
        "/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/judgments",
        response_model=QrelsSet,
    )
    def save_qrels_judgments(
        project_id: str,
        qrels_id: str,
        request: QrelsJudgmentBatch,
    ) -> QrelsSet:
        try:
            repository.get(project_id)
            qrels = qrels_sets.get(qrels_id)
        except (ProjectNotFoundError, LookupError) as exc:
            raise HTTPException(status_code=404, detail="qrels 不存在") from exc
        if qrels.project_id != project_id:
            raise HTTPException(status_code=404, detail="qrels 不属于当前项目")
        try:
            return qrels_service.save_judgments(qrels, request)
        except QrelsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post(
        "/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/freeze",
        response_model=QrelsSet,
    )
    def freeze_qrels(project_id: str, qrels_id: str) -> QrelsSet:
        try:
            repository.get(project_id)
            qrels = qrels_sets.get(qrels_id)
        except (ProjectNotFoundError, LookupError) as exc:
            raise HTTPException(status_code=404, detail="qrels 不存在") from exc
        if qrels.project_id != project_id:
            raise HTTPException(status_code=404, detail="qrels 不属于当前项目")
        try:
            return qrels_service.freeze(qrels)
        except QrelsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get(
        "/api/v1/projects/{project_id}/experiments/generation-runs/latest",
        response_model=GenerationBatchRun | None,
    )
    def latest_generation_run(project_id: str) -> GenerationBatchRun | None:
        try:
            repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        return generation_runs.latest(project_id)

    @application.post(
        "/api/v1/projects/{project_id}/experiments/generation-runs",
        response_model=GenerationBatchRun,
        status_code=status.HTTP_201_CREATED,
    )
    async def run_generation_batch(
        project_id: str,
        request: GenerationBatchRequest,
    ) -> GenerationBatchRun:
        try:
            project = repository.get(project_id)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        experiment = experiment_runs.latest(project_id)
        literature = literature_runs.latest(project_id)
        qrels = qrels_sets.latest(project_id)
        if experiment is None or literature is None:
            raise HTTPException(status_code=409, detail="缺少实验协议或文献上游产物")
        try:
            return await generation_service.run(project, experiment, literature, qrels, request)
        except GenerationBenchmarkError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get(
        "/api/v1/projects/{project_id}/experiments/generation-runs/{run_id}/log",
        response_class=FileResponse,
    )
    def download_generation_log(project_id: str, run_id: str) -> FileResponse:
        try:
            repository.get(project_id)
            run = generation_runs.get(run_id)
        except (ProjectNotFoundError, LookupError) as exc:
            raise HTTPException(status_code=404, detail="生成批量运行不存在") from exc
        if run.project_id != project_id or run.result is None:
            raise HTTPException(status_code=404, detail="生成批量运行不存在或尚未完成")
        data_root = resolved.data_dir.resolve()
        log_path = (data_root / run.result.log_manifest.relative_path).resolve()
        if not log_path.is_relative_to(data_root) or not log_path.is_file():
            raise HTTPException(status_code=404, detail="生成 JSONL 不存在")
        return FileResponse(
            log_path,
            media_type="application/x-ndjson",
            filename=f"generation-{run.id}.jsonl",
        )

    @application.post(
        "/api/v1/projects/{project_id}/transitions",
        response_model=ResearchProject,
    )
    def transition_project(project_id: str, request: StageTransition) -> ResearchProject:
        try:
            return repository.transition(project_id, request.target_stage)
        except ProjectNotFoundError as exc:
            raise HTTPException(status_code=404, detail="科研项目不存在") from exc
        except InvalidStageTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return application


app = create_app()


def run() -> None:
    uvicorn.run("syt_platform.api.main:app", host="127.0.0.1", port=8000)
