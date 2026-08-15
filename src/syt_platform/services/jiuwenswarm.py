"""JiuwenSwarm 运行时适配器。"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx


def _dotenv_keys(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


@dataclass(frozen=True, slots=True)
class JiuwenSwarmStatus:
    initialized: bool
    model_configured: bool
    lite_mode: bool
    ports: dict[int, bool]


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    api_base: str
    model_name: str
    model_provider: str
    custom_headers: str
    embed_api_base: str
    embed_model: str
    has_api_key: bool
    has_embed_api_key: bool
    has_jina_api_key: bool
    has_serper_api_key: bool
    has_perplexity_api_key: bool
    has_openalex_api_key: bool


@dataclass(frozen=True, slots=True)
class ModelConnectionResult:
    ok: bool
    message: str
    status_code: int | None = None


class JiuwenSwarmAdapter:
    PORTS = (5173, 18092, 19000, 19001)

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    @property
    def env_path(self) -> Path:
        return self.data_dir / "config" / ".env"

    def _env_values(self) -> dict[str, str]:
        return _dotenv_keys(self.env_path)

    def status(self) -> JiuwenSwarmStatus:
        env_values = self._env_values()
        required = {
            key: env_values.get(key, "").strip()
            for key in ("API_BASE", "API_KEY", "MODEL_NAME", "MODEL_PROVIDER")
        }
        placeholder_markers = ("example.com", "replace-with", "xxxxxxxx", "your-model")
        configured = all(required.values()) and not any(
            marker in value.lower()
            for value in required.values()
            for marker in placeholder_markers
        )
        lite_mode = env_values.get("SUYITONG_LITE_MODE", "").lower() in {
            "1", "true", "yes", "on"
        }
        return JiuwenSwarmStatus(
            initialized=(self.data_dir / "config" / "config.yaml").exists(),
            model_configured=configured,
            lite_mode=lite_mode,
            ports={port: _port_open(port) for port in self.PORTS},
        )

    def model_configuration(self) -> ModelConfiguration:
        values = self._env_values()
        return ModelConfiguration(
            api_base=values.get("API_BASE", ""),
            model_name=values.get("MODEL_NAME", ""),
            model_provider=values.get("MODEL_PROVIDER", "OpenAI") or "OpenAI",
            custom_headers=values.get("CUSTOM_HEADERS", ""),
            embed_api_base=values.get("EMBED_API_BASE", ""),
            embed_model=values.get("EMBED_MODEL", ""),
            has_api_key=bool(values.get("API_KEY", "").strip()),
            has_embed_api_key=bool(values.get("EMBED_API_KEY", "").strip()),
            has_jina_api_key=bool(values.get("JINA_API_KEY", "").strip()),
            has_serper_api_key=bool(values.get("SERPER_API_KEY", "").strip()),
            has_perplexity_api_key=bool(values.get("PERPLEXITY_API_KEY", "").strip()),
            has_openalex_api_key=bool(values.get("OPENALEX_API_KEY", "").strip()),
        )

    def update_environment(self, updates: dict[str, str | None]) -> ModelConfiguration:
        """更新受管环境变量；空的密钥字段会保留原值。"""

        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        original = self.env_path.read_text(encoding="utf-8") if self.env_path.exists() else ""
        lines = original.splitlines()
        remaining = dict(updates)
        secret_keys = {
            "API_KEY",
            "EMBED_API_KEY",
            "JINA_API_KEY",
            "SERPER_API_KEY",
            "PERPLEXITY_API_KEY",
            "OPENALEX_API_KEY",
        }
        rendered: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in remaining:
                    value = remaining.pop(key)
                    if key in secret_keys and not value:
                        rendered.append(line)
                    else:
                        rendered.append(f"{key}={value or ''}")
                    continue
            rendered.append(line)
        for key, value in remaining.items():
            if key in secret_keys and not value:
                continue
            rendered.append(f"{key}={value or ''}")
        temporary = self.env_path.with_suffix(".env.tmp")
        temporary.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
        temporary.replace(self.env_path)
        return self.model_configuration()

    def test_model_connection(self) -> ModelConnectionResult:
        values = self._env_values()
        api_base = values.get("API_BASE", "").strip().rstrip("/") + "/"
        api_key = values.get("API_KEY", "").strip()
        model_name = values.get("MODEL_NAME", "").strip()
        if not api_base.strip("/") or not api_key or not model_name:
            return ModelConnectionResult(False, "请先填写 API 地址、密钥和模型名称")
        if not api_base.startswith(("http://", "https://")):
            return ModelConnectionResult(False, "API 地址必须以 http:// 或 https:// 开头")

        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        try:
            response = httpx.get(
                urljoin(api_base, "models"),
                headers=headers,
                timeout=12,
                follow_redirects=True,
            )
            if response.is_success:
                return ModelConnectionResult(True, "模型服务连接成功", response.status_code)
            return ModelConnectionResult(
                False,
                f"模型服务返回 HTTP {response.status_code}",
                response.status_code,
            )
        except httpx.HTTPError as exc:
            return ModelConnectionResult(False, f"连接失败：{exc.__class__.__name__}")
