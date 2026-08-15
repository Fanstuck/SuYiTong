from pathlib import Path

from fastapi.testclient import TestClient

from syt_platform.api.main import create_app
from syt_platform.config import Settings


def test_create_and_list_project(tmp_path: Path) -> None:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        jiuwenswarm_data_dir=tmp_path / ".jiuwenswarm",
    )
    client = TestClient(create_app(settings))

    response = client.post(
        "/api/v1/projects",
        json={
            "title": "可溯源上下文记忆",
            "research_direction": "Agent Context Engineering",
            "mode": "semi",
        },
    )
    assert response.status_code == 201
    assert response.json()["stage"] == "intake"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_environment_configuration_never_returns_secrets(tmp_path: Path) -> None:
    swarm_dir = tmp_path / ".jiuwenswarm"
    (swarm_dir / "config").mkdir(parents=True)
    (swarm_dir / "config" / "config.yaml").write_text(
        "preferred_language: zh\n", encoding="utf-8"
    )
    (swarm_dir / "config" / ".env").write_text(
        "API_BASE=\nAPI_KEY=\nMODEL_NAME=\nMODEL_PROVIDER=OpenAI\n",
        encoding="utf-8",
    )
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        jiuwenswarm_data_dir=swarm_dir,
    )
    client = TestClient(create_app(settings))

    saved = client.put(
        "/api/v1/system/environment",
        json={
            "api_base": "https://models.example.test/v1",
            "api_key": "sk-private-value",
            "model_name": "research-model",
            "model_provider": "OpenAI",
            "embed_api_base": "https://embeddings.example.test/v1",
            "embed_model": "test-embedding",
            "embed_api_key": "embed-private-value",
            "openalex_api_key": "oa-private-value",
        },
    )

    assert saved.status_code == 200
    assert saved.json()["has_api_key"] is True
    assert "sk-private-value" not in saved.text
    assert saved.json()["has_openalex_api_key"] is True
    assert "oa-private-value" not in saved.text
    assert saved.json()["has_embed_api_key"] is True
    assert "embed-private-value" not in saved.text
    fetched = client.get("/api/v1/system/environment")
    assert fetched.status_code == 200
    assert "api_key" not in fetched.json()
    assert "sk-private-value" not in fetched.text
    assert "openalex_api_key" not in fetched.json()
    assert "oa-private-value" not in fetched.text
    assert "embed_api_key" not in fetched.json()
    assert "embed-private-value" not in fetched.text


def test_console_is_served(tmp_path: Path) -> None:
    settings = Settings(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "test.db",
        jiuwenswarm_data_dir=tmp_path / ".jiuwenswarm",
    )
    response = TestClient(create_app(settings)).get("/")

    assert response.status_code == 200
    assert "速易通" in response.text
