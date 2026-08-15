import hashlib
import math
from pathlib import Path

from fastapi.testclient import TestClient

from syt_platform.api.main import create_app
from syt_platform.config import Settings
from syt_platform.domain.literature import LiteratureSynthesis, PaperRecord
from syt_platform.services.model_gateway import StructuredGeneration
from syt_platform.services.embedding import EmbeddingBatch, EmbeddingConnectionResult


class FakeSearchService:
    async def search(self, queries: list[str]) -> list[PaperRecord]:
        return [
            PaperRecord(
                id=f"PAPER-{index:03d}",
                title=f"Traceable agent memory study {index}",
                authors=["Researcher A", "Researcher B"],
                year=2020 + index,
                venue="Agent Research Conference",
                doi=f"10.1000/test.{index}",
                url=f"https://doi.org/10.1000/test.{index}",
                abstract="This study evaluates provenance-aware memory retrieval.",
                cited_by_count=index,
                source="OpenAlex+Crossref",
                source_record_id=f"W{index}",
                matched_query=queries[0],
                relevance_score=10.0 - index,
            )
            for index in range(1, 9)
        ]


class FakeResearchGateway:
    @property
    def model_name(self) -> str:
        return "test-model"

    async def generate_json(self, **kwargs: object) -> StructuredGeneration:
        operation = kwargs.get("operation")
        if operation == "pacm_sw_topic_framing":
            data = {
                "research_identity": "PACM-SW",
                "requirements_summary": "统一上下文工程和记忆引擎。",
                "candidate_titles": [
                    {
                        "title_cn": "可溯源上下文记忆",
                        "title_en": "Provenance-Aware Context Memory",
                        "focus": "Agent scientific writing",
                    }
                ],
                "problem_statement": "科研智能体记忆缺少来源。",
                "research_gap_hypotheses": ["来源映射可能不足。"],
                "research_questions": ["来源感知检索是否有效？"],
                "proposed_contributions": ["提出可溯源记忆框架。"],
                "method_positioning": "上下文与记忆统一。",
                "keywords_cn": ["可溯源记忆"],
                "keywords_en": ["provenance aware agent memory"],
                "literature_search_queries": ["provenance aware agent memory"],
            }
        elif operation == "pacm_sw_literature_review":
            data = {
                "review_scope": "Agent memory and context provenance",
                "executive_summary": "检索记录显示相关工作覆盖记忆检索与来源追踪。",
                "themes": [
                    {
                        "name": "Agent memory",
                        "description": "智能体记忆检索。",
                        "paper_ids": ["PAPER-001", "UNKNOWN"],
                    }
                ],
                "key_findings": [
                    {
                        "claim": "来源信息有助于审计。",
                        "paper_ids": ["PAPER-001", "PAPER-002"],
                        "verification_status": "evidence_supported",
                        "confidence": "medium",
                    }
                ],
                "validated_gap_hypotheses": [
                    {
                        "claim": "科研写作场景仍需进一步验证。",
                        "paper_ids": ["PAPER-003"],
                        "verification_status": "partially_supported",
                        "confidence": "low",
                    }
                ],
                "contradictions": [],
                "related_work_draft": "已有研究讨论智能体记忆 [PAPER-001]。",
                "method_implications": ["保留来源账本。"],
                "search_limitations": ["仅检索两个元数据源。"],
                "quality_gate_checklist": ["确认核心文献。"],
            }
        elif operation == "pacm_sw_method_design":
            data = {
                "method_name": "PACM-SW",
                "method_summary": "以来源契约约束分层记忆检索。",
                "problem_formulation": "在有限预算下选择可追溯上下文。",
                "novelty_boundary": "组合与科研写作场景贡献，尚待实验验证。",
                "components": [
                    {
                        "id": f"C{index}",
                        "name": f"Component {index}",
                        "purpose": "测试组件",
                        "inputs": ["memory"],
                        "outputs": ["context"],
                        "algorithm_steps": ["读取", "验证"],
                        "evidence_ids": ["PAPER-001", "UNKNOWN"],
                    }
                    for index in range(1, 6)
                ],
                "memory_layers": [
                    {
                        "name": name,
                        "content_types": ["Evidence"],
                        "write_policy": "质量门后写入",
                        "retrieval_role": "支持任务上下文",
                        "provenance_required": True,
                    }
                    for name in ["Global", "State", "Evidence", "Episode"]
                ],
                "provenance_contract": {
                    "entities": ["Claim", "Evidence", "Decision", "Experiment"],
                    "relations": ["SUPPORTED_BY"],
                    "required_fields": ["source_id", "version"],
                    "invariants": ["Claim 必须关联 Evidence"],
                },
                "retrieval_objective": {
                    "formula": "S = relevance + provenance - conflict",
                    "terms": [
                        {
                            "symbol": "p",
                            "name": "provenance",
                            "definition": "来源完整度",
                            "optimization_note": "开发集调参",
                        }
                    ],
                    "candidate_generation": ["BM25", "vector", "graph"],
                    "budget_policy": "不超过阶段 token 预算",
                    "tie_break_policy": "优先来源完整且较新的记录",
                },
                "context_assembly_protocol": ["任务契约", "批准决策", "证据", "限制"],
                "multi_agent_protocol": ["写入提案", "证据验证", "质量门提交"],
                "experiment_designs": [
                    {
                        "id": f"E{index}",
                        "research_question": f"RQ{index}",
                        "falsifiable_hypothesis": "PACM-SW 可能改善目标指标。",
                        "baselines": ["B0", "B2", "Ours"],
                        "primary_metrics": ["Claim Support Rate"],
                        "controls": ["相同模型与任务"],
                        "falsification_condition": "置信区间不支持改善或方向相反。",
                    }
                    for index in range(1, 5)
                ],
                "ablations": [f"Ablation {index}" for index in range(1, 7)],
                "implementation_contracts": ["每次检索记录 trace id"],
                "evidence_design_links": [
                    {
                        "design_claim": "保留来源信息",
                        "paper_ids": ["PAPER-001", "UNKNOWN"],
                        "rationale": "文献支持来源追踪。",
                        "confidence": "medium",
                    }
                ],
                "risks_and_limitations": ["当前仅摘要级证据。"],
                "quality_gate_checklist": ["公式可实现", "实验可证伪"],
            }
        elif operation == "b1_planner_generation":
            data = {
                "plan": ["先定义问题", "再综合证据"],
                "decisions": ["保留来源"],
                "evidence_ids": ["PAPER-001"],
            }
        elif operation in {
            "b0_single_agent_generation",
            "b1_writer_generation",
            "b1_reviewer_generation",
        }:
            data = {
                "final_text": "保留来源并基于证据形成学术产物 [PAPER-001]。",
                "citations": ["PAPER-001"],
                "decisions": ["保留来源"],
            }
        else:
            data = {
                "objective": "验证 PACM-SW 的引用真实性与上下文效率。",
                "validation_scope": "预注册协议与技术验证集。",
                "systems": [
                    {
                        "id": system_id,
                        "name": system_id,
                        "description": "对照配置",
                        "memory_strategy": "configured memory",
                        "retrieval_strategy": "configured retrieval",
                        "provenance_enforced": system_id == "Ours",
                        "role_aware": system_id == "Ours",
                        "graph_enabled": system_id == "Ours",
                        "conflict_detection": system_id == "Ours",
                        "context_budget_tokens": 6000,
                    }
                    for system_id in ["B0", "B1", "B2", "B3", "Ours"]
                ],
                "tasks": [
                    {
                        "id": f"TASK-{index:02d}",
                        "name": f"Task {index}",
                        "task_type": "evidence_synthesis",
                        "input_contract": "固定查询与文献集合",
                        "expected_artifact": "Claim 列表",
                        "success_criteria": ["引用有效"],
                        "required_evidence_ids": ["PAPER-001", "UNKNOWN"],
                    }
                    for index in range(1, 5)
                ],
                "metrics": [
                    {
                        "name": "Reference Validity",
                        "formula_or_procedure": "valid / all",
                        "direction": "higher",
                        "deterministic": True,
                        "required_inputs": ["references"],
                    }
                ],
                "ablations": [f"R{index}" for index in range(1, 7)],
                "fairness_controls": ["相同模型与预算"],
                "seeds": [13, 37, 73],
                "repetitions": 3,
                "statistics_plan": ["配对比较与置信区间"],
                "execution_order": ["冻结", "运行", "审计"],
                "resource_budget": ["限制总调用次数"],
                "stop_conditions": ["超预算停止"],
                "reproducibility_manifest": ["保存配置和原始结果"],
                "quality_gate_checklist": ["基线与消融全部完成"],
            }
        return StructuredGeneration(
            data=data,
            model_name=self.model_name,
            usage={"total": {"total_tokens": 800}},
        )


class FakeEmbeddingGateway:
    @property
    def model_name(self) -> str:
        return "test-embedding"

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            raw = [float(digest[index] + 1) for index in range(8)]
            norm = math.sqrt(sum(item * item for item in raw))
            vectors.append([item / norm for item in raw])
        return EmbeddingBatch(
            model=self.model_name,
            vectors=vectors,
            dimension=8,
            cache_hits=0,
            api_calls=1,
            latency_ms=1.25,
        )

    async def test_connection(self) -> EmbeddingConnectionResult:
        return EmbeddingConnectionResult(
            ok=True,
            message="Embedding 服务连接正常",
            model=self.model_name,
            dimension=8,
            latency_ms=1.25,
        )


def test_literature_review_vertical_slice(tmp_path: Path) -> None:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        jiuwenswarm_data_dir=tmp_path / ".jiuwenswarm",
    )
    client = TestClient(
        create_app(
            settings,
            model_gateway=FakeResearchGateway(),
            academic_search=FakeSearchService(),
            embedding_gateway=FakeEmbeddingGateway(),
        )
    )
    project = client.post(
        "/api/v1/projects",
        json={"title": "可溯源科研记忆", "research_direction": "Agent Memory"},
    ).json()
    topic_run = client.post(
        f"/api/v1/projects/{project['id']}/topic-framing/runs"
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/topic-framing/confirm",
        json={"selected_candidate_index": 0},
    )

    generated = client.post(
        f"/api/v1/projects/{project['id']}/literature-review/runs"
    )

    assert generated.status_code == 201
    run = generated.json()
    assert run["topic_run_id"] == topic_run["id"]
    assert run["status"] == "completed"
    assert len(run["papers"]) == 8
    assert run["result"]["themes"][0]["paper_ids"] == ["PAPER-001"]
    assert len(run["execution_trace"]) == 4

    confirmed = client.post(
        f"/api/v1/projects/{project['id']}/literature-review/confirm",
        json={"review_notes": "文献范围通过首轮审查"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["project"]["stage"] == "method_design"
    assert confirmed.json()["run"]["confirmed_at"] is not None

    method_generated = client.post(
        f"/api/v1/projects/{project['id']}/method-design/runs"
    )
    assert method_generated.status_code == 201
    method_run = method_generated.json()
    assert method_run["status"] == "completed"
    assert len(method_run["result"]["components"]) == 5
    assert method_run["result"]["components"][0]["evidence_ids"] == ["PAPER-001"]
    assert "H3" in method_run["result"]["risks_and_limitations"][-1]

    method_confirmed = client.post(
        f"/api/v1/projects/{project['id']}/method-design/confirm",
        json={"review_notes": "方法设计进入实验实现"},
    )
    assert method_confirmed.status_code == 200
    assert method_confirmed.json()["project"]["stage"] == "experiment"

    experiment_generated = client.post(
        f"/api/v1/projects/{project['id']}/experiments/runs"
    )
    assert experiment_generated.status_code == 201
    experiment_run = experiment_generated.json()
    assert experiment_run["status"] == "completed"
    assert experiment_run["result"]["benchmark_status"] == "formal_benchmark_pending"
    assert experiment_run["result"]["efficacy_claim_allowed"] is False
    assert len(experiment_run["result"]["protocol"]["systems"]) == 5
    assert len(experiment_run["result"]["pilot_results"]) == 3
    assert experiment_run["result"]["protocol"]["tasks"][0]["required_evidence_ids"] == ["PAPER-001"]
    assert experiment_run["result"]["protocol"]["statistics_plan"]
    assert experiment_run["result"]["protocol"]["execution_order"]
    assert experiment_run["result"]["protocol"]["resource_budget"]
    assert experiment_run["result"]["protocol"]["stop_conditions"]
    assert experiment_run["result"]["protocol"]["reproducibility_manifest"]
    assert experiment_run["result"]["protocol"]["quality_gate_checklist"]
    assert sum(item["status"] == "pass" for item in experiment_run["result"]["preflight_checks"]) == 5
    assert sum(item["status"] == "block" for item in experiment_run["result"]["preflight_checks"]) == 1

    retrieval_generated = client.post(
        f"/api/v1/projects/{project['id']}/experiments/retrieval-runs",
        json={"role": "reviewer", "top_k": 5, "context_budget_tokens": 6000},
    )
    assert retrieval_generated.status_code == 201
    retrieval_run = retrieval_generated.json()
    assert retrieval_run["status"] == "completed"
    assert [item["system_id"] for item in retrieval_run["result"]["systems"]] == [
        "B2", "B3", "Ours"
    ]
    assert retrieval_run["result"]["systems"][0]["implementation_level"] == (
        "real_dense_embedding_retrieval"
    )
    assert retrieval_run["result"]["benchmark_status"] == (
        "retrieval_engines_implemented_formal_benchmark_pending"
    )
    assert retrieval_run["result"]["efficacy_claim_allowed"] is False
    manifest = retrieval_run["result"]["log_manifest"]
    assert manifest["schema_version"] == "syt-retrieval-jsonl-v1"
    assert manifest["record_count"] == 5
    assert len(manifest["sha256"]) == 64
    downloaded = client.get(
        f"/api/v1/projects/{project['id']}/experiments/retrieval-runs/"
        f"{retrieval_run['id']}/log"
    )
    assert downloaded.status_code == 200
    records = [item for item in downloaded.text.splitlines() if item]
    assert len(records) == manifest["record_count"]

    qrels_created = client.post(
        f"/api/v1/projects/{project['id']}/experiments/qrels",
        json={"assessor_id": "human-reviewer", "pool_depth": 5},
    )
    assert qrels_created.status_code == 201
    qrels = qrels_created.json()
    assert qrels["status"] == "draft"
    assert qrels["judgment_count"] == 0
    judgments = [
        {
            "query": item["query"],
            "paper_id": item["paper_id"],
            "relevance": 3 if index == 0 else 0,
            "rationale": "人工测试标注",
        }
        for index, item in enumerate(qrels["items"])
    ]
    saved_qrels = client.put(
        f"/api/v1/projects/{project['id']}/experiments/qrels/{qrels['id']}/judgments",
        json={"assessor_id": "human-reviewer", "judgments": judgments},
    )
    assert saved_qrels.status_code == 200
    assert saved_qrels.json()["judgment_count"] == len(qrels["items"])
    frozen_qrels = client.post(
        f"/api/v1/projects/{project['id']}/experiments/qrels/{qrels['id']}/freeze"
    )
    assert frozen_qrels.status_code == 200
    assert frozen_qrels.json()["status"] == "frozen"
    assert len(frozen_qrels.json()["frozen_sha256"]) == 64

    ablation_batch = client.post(
        f"/api/v1/projects/{project['id']}/experiments/retrieval-runs",
        json={
            "role": "researcher",
            "top_k": 5,
            "context_budget_tokens": 6000,
            "seeds": [13, 37, 73],
            "include_ablations": True,
            "evaluation_mode": "formal",
        },
    )
    assert ablation_batch.status_code == 201
    ablation_run = ablation_batch.json()
    assert len(ablation_run["result"]["systems"]) == 9
    assert ablation_run["result"]["log_manifest"]["record_count"] == 29
    assert all(
        len(item["query_results"]) == 3 for item in ablation_run["result"]["systems"]
    )
    assert ablation_run["result"]["engine_checks"][5]["status"] == "pass"
    assert ablation_run["result"]["engine_checks"][6]["status"] == "pass"
    assert ablation_run["result"]["engine_checks"][7]["status"] == "pass"

    generation_batch = client.post(
        f"/api/v1/projects/{project['id']}/experiments/generation-runs",
        json={
            "seeds": [13],
            "task_limit": 1,
            "context_budget_tokens": 3000,
            "mode": "engineering",
        },
    )
    assert generation_batch.status_code == 201
    generation_run = generation_batch.json()
    assert [item["system_id"] for item in generation_run["result"]["systems"]] == [
        "B0", "B1"
    ]
    assert len(generation_run["result"]["cells"]) == 2
    assert generation_run["result"]["systems"][0]["mean_valid_citation_rate"] == 1.0
    assert generation_run["result"]["provider_seed_enforced"] is False

    blocked_confirmation = client.post(
        f"/api/v1/projects/{project['id']}/experiments/confirm",
        json={"review_notes": "尝试进入写作"},
    )
    assert blocked_confirmation.status_code == 409


def test_literature_synthesis_normalizes_provider_list_variants() -> None:
    synthesis = LiteratureSynthesis.model_validate(
        {
            "review_scope": {"description": "scope"},
            "executive_summary": "summary",
            "themes": [],
            "key_findings": [],
            "validated_gap_hypotheses": [],
            "contradictions": [],
            "related_work_draft": "draft",
            "method_implications": "implication",
            "search_limitations": "limitation",
            "quality_gate_checklist": {"citations_checked": True},
        }
    )
    assert synthesis.method_implications == ["implication"]
    assert synthesis.review_scope == "scope"
    assert synthesis.search_limitations == ["limitation"]
    assert synthesis.quality_gate_checklist == ["citations_checked: 通过"]
