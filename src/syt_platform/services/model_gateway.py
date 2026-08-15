"""通过 JiuwenSwarm/openJiuwen 模型栈调用第三方推理 API。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import certifi

# OpenJiuwen 的严格证书读取标志在 Windows 中不存在；值 0 保留普通只读打开，
# TLS 证书本身仍由严格 SSLContext 验证。
if os.name == "nt":
    if not hasattr(os, "O_NOFOLLOW"):
        os.O_NOFOLLOW = 0  # type: ignore[attr-defined]
    if not hasattr(os, "O_CLOEXEC"):
        os.O_CLOEXEC = 0  # type: ignore[attr-defined]
from jiuwenswarm.symphony.llm import (
    LLMConfig,
    create_llm_client,
    get_llm_token_usage_summary,
    llm_usage_context,
    reset_llm_token_usage,
)

from syt_platform.services.jiuwenswarm import _dotenv_keys


class ModelGatewayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StructuredGeneration:
    data: dict[str, Any]
    model_name: str
    usage: dict[str, Any]


class JiuwenModelGateway:
    """保留 JiuwenSwarm 模型配置和 token 统计语义的结构化生成网关。"""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def _configuration(self) -> tuple[LLMConfig, str]:
        values = _dotenv_keys(self.data_dir / "config" / ".env")
        model_name = values.get("MODEL_NAME", "").strip()
        api_base = values.get("API_BASE", "").strip().rstrip("/")
        api_key = values.get("API_KEY", "").strip()
        provider = values.get("MODEL_PROVIDER", "OpenAI").strip() or "OpenAI"
        verify_ssl = values.get("JIUWENSWARM_SSL_VERIFY", "true").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        ssl_cert = values.get("JIUWENSWARM_SSL_CERT", "").strip() or certifi.where()
        if verify_ssl:
            os.environ["SAFE_CERT_DIR"] = str(Path(ssl_cert).resolve().parent)
        if not all((model_name, api_base, api_key)):
            raise ModelGatewayError("主推理模型尚未完成配置")
        config = LLMConfig(
            model=model_name,
            model_client_config={
                "model_name": model_name,
                "api_base": api_base,
                "api_key": api_key,
                "client_provider": provider,
                "verify_ssl": verify_ssl,
                "ssl_cert": ssl_cert if verify_ssl else None,
            },
            model_config_obj={"model": model_name},
            temperature=0.2,
            top_p=0.9,
        )
        return config, model_name

    @property
    def model_name(self) -> str:
        _, model_name = self._configuration()
        return model_name

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        operation: str,
        stage: str = "research",
        max_tokens: int = 4000,
    ) -> StructuredGeneration:
        config, model_name = self._configuration()
        client = create_llm_client(config)
        reset_llm_token_usage()
        try:
            with llm_usage_context(stage, operation):
                content = await client.complete_json_async(
                    system_prompt=system_prompt,
                    user_content=user_prompt,
                    timeout=90,
                    error_context=operation,
                    request_overrides={"max_tokens": max_tokens},
                )
            data = json.loads(content)
        except Exception as exc:
            raise ModelGatewayError(f"JiuwenSwarm 模型调用失败：{exc}") from exc
        # Some OpenAI-compatible reasoning endpoints wrap a single JSON object
        # in a one-element array. Accept that harmless envelope, but never guess
        # among multiple objects.
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            data = data[0]
        if not isinstance(data, dict):
            raise ModelGatewayError("模型没有返回 JSON 对象")
        return StructuredGeneration(
            data=data,
            model_name=model_name,
            usage=get_llm_token_usage_summary(),
        )
