from pathlib import Path

from syt_platform.services.jiuwenswarm import JiuwenSwarmAdapter


def test_placeholder_credentials_are_not_treated_as_configured(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("preferred_language: zh\n", encoding="utf-8")
    (config_dir / ".env").write_text(
        "API_BASE=https://api.example.com/v1\n"
        "API_KEY=sk-xxxxxxxxx\n"
        "MODEL_NAME=your-model-name\n"
        "MODEL_PROVIDER=OpenAI\n"
        "SUYITONG_LITE_MODE=true\n",
        encoding="utf-8",
    )

    status = JiuwenSwarmAdapter(tmp_path).status()

    assert status.initialized is True
    assert status.model_configured is False
    assert status.lite_mode is True


def test_blank_secret_update_preserves_existing_value(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    env_path = config_dir / ".env"
    env_path.write_text(
        "# managed configuration\n"
        "API_BASE=https://old.example/v1\n"
        "API_KEY=fixture-model-token\n"
        "OPENALEX_API_KEY=fixture-openalex-token\n"
        "MODEL_NAME=old-model\n",
        encoding="utf-8",
    )
    adapter = JiuwenSwarmAdapter(tmp_path)

    updated = adapter.update_environment(
        {
            "API_BASE": "https://new.example/v1",
            "API_KEY": None,
            "MODEL_NAME": "new-model",
            "OPENALEX_API_KEY": None,
        }
    )

    assert updated.api_base == "https://new.example/v1"
    assert updated.model_name == "new-model"
    assert updated.has_api_key is True
    assert "API_KEY=fixture-model-token" in env_path.read_text(encoding="utf-8")
    assert updated.has_openalex_api_key is True
    assert "OPENALEX_API_KEY=fixture-openalex-token" in env_path.read_text(encoding="utf-8")
