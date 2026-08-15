from pathlib import Path

from fastapi.testclient import TestClient

from syt_platform.api.main import create_app
from syt_platform.config import Settings
from syt_platform.services.model_gateway import StructuredGeneration


class FakeModelGateway:
    @property
    def model_name(self) -> str:
        return "test-research-model"

    async def generate_json(self, **_: object) -> StructuredGeneration:
        return StructuredGeneration(
            model_name=self.model_name,
            usage={"total": {"total_tokens": 321}},
            data={
                "research_identity": "PACM-SW 可溯源上下文记忆研究",
                "requirements_summary": "面向多智能体科研写作的上下文与记忆统一方法。",
                "candidate_titles": [
                    {
                        "title_cn": "面向科研写作的可溯源上下文记忆",
                        "title_en": "Provenance-Aware Context Memory for Scientific Writing",
                        "focus": "来源追踪与记忆检索",
                    }
                ],
                "problem_statement": "长流程科研写作中的上下文容易丢失来源与演化关系。",
                "research_gap_hypotheses": ["现有方法可能缺少细粒度来源关联。"],
                "research_questions": ["来源感知检索能否提高证据一致性？"],
                "proposed_contributions": ["提出 PACM-SW 方法框架。"],
                "method_positioning": "统一上下文工程和记忆引擎。",
                "core_modules": ["来源账本", "分层检索"],
                "non_goals": ["首篇论文不验证自演进"],
                "keywords_cn": ["上下文工程", "记忆引擎"],
                "keywords_en": ["context engineering", "memory engine"],
                "literature_search_queries": ["provenance aware agent memory"],
                "novelty_risks": ["PACM 名称可能重名"],
                "evidence_boundary": ["尚未完成文献检索"],
                "provenance_map": [
                    {
                        "statement": "统一上下文工程和记忆引擎",
                        "context_ids": ["CTX-CORE-001", "UNKNOWN"],
                        "verification_status": "context_supported",
                    }
                ],
                "quality_gate_checklist": ["确认研究问题可实验验证"],
            },
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        jiuwenswarm_data_dir=tmp_path / ".jiuwenswarm",
    )


def test_topic_framing_vertical_slice(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path), model_gateway=FakeModelGateway()))
    project = client.post(
        "/api/v1/projects",
        json={
            "title": "面向长上下文任务的分层记忆检索方法",
            "research_direction": "Agent 记忆引擎与上下文工程",
            "mode": "semi",
        },
    ).json()

    generated = client.post(
        f"/api/v1/projects/{project['id']}/topic-framing/runs"
    )

    assert generated.status_code == 201
    run = generated.json()
    assert run["status"] == "completed"
    assert run["model_name"] == "test-research-model"
    assert run["result"]["candidate_titles"]
    assert run["result"]["provenance_map"][0]["context_ids"] == ["CTX-CORE-001"]
    assert len(run["execution_trace"]) == 4

    latest = client.get(
        f"/api/v1/projects/{project['id']}/topic-framing/runs/latest"
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == run["id"]

    confirmed = client.post(
        f"/api/v1/projects/{project['id']}/topic-framing/confirm",
        json={"selected_candidate_index": 0, "review_notes": "通过首轮质量门"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["project"]["stage"] == "literature_review"
    assert confirmed.json()["run"]["confirmed_at"] is not None


def test_topic_confirmation_requires_generated_artifact(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path), model_gateway=FakeModelGateway()))
    project = client.post(
        "/api/v1/projects",
        json={"title": "上下文记忆实验", "research_direction": "Agent Memory"},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/topic-framing/confirm",
        json={"selected_candidate_index": 0},
    )

    assert response.status_code == 409
