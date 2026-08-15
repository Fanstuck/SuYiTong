"""OpenAI-compatible Embedding 客户端与本地向量缓存。"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import ssl
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import certifi
import httpx

from syt_platform.services.jiuwenswarm import _dotenv_keys


class EmbeddingGatewayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    model: str
    vectors: list[list[float]]
    dimension: int
    cache_hits: int
    api_calls: int
    latency_ms: float


@dataclass(frozen=True, slots=True)
class EmbeddingConnectionResult:
    ok: bool
    message: str
    model: str = ""
    dimension: int | None = None
    latency_ms: float | None = None


class EmbeddingCache:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    cache_key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def key(model: str, text: str) -> str:
        payload = f"{model}\0{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def get(self, model: str, text: str) -> list[float] | None:
        cache_key = self.key(model, text)
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT vector_json FROM embedding_cache WHERE cache_key = ? AND model = ?",
                (cache_key, model),
            ).fetchone()
        return [float(item) for item in json.loads(row[0])] if row else None

    def put(self, model: str, text: str, vector: list[float]) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO embedding_cache
                    (cache_key, model, dimension, vector_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.key(model, text),
                    model,
                    len(vector),
                    json.dumps(vector, separators=(",", ":")),
                    datetime.now(UTC).isoformat(),
                ),
            )


class OpenAIEmbeddingGateway:
    """通过用户配置的第三方 API 生成真实向量；密钥只从本地 env 读取。"""

    def __init__(self, data_dir: Path, cache_path: Path) -> None:
        self.data_dir = data_dir
        self.cache = EmbeddingCache(cache_path)

    def _configuration(self) -> tuple[str, str, str, dict[str, str], bool]:
        values = _dotenv_keys(self.data_dir / "config" / ".env")
        api_base = values.get("EMBED_API_BASE", "").strip().rstrip("/")
        api_key = values.get("EMBED_API_KEY", "").strip()
        model = values.get("EMBED_MODEL", "").strip()
        if not all((api_base, api_key, model)):
            raise EmbeddingGatewayError("Embedding API Base、模型或 API Key 尚未完整配置")
        endpoint = api_base if api_base.endswith("/embeddings") else f"{api_base}/embeddings"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        custom = values.get("CUSTOM_HEADERS", "").strip()
        if custom:
            try:
                parsed = json.loads(custom)
                if isinstance(parsed, dict):
                    headers.update({str(key): str(value) for key, value in parsed.items()})
            except json.JSONDecodeError:
                for line in custom.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers[key.strip()] = value.strip()
        verify_ssl = values.get("JIUWENSWARM_SSL_VERIFY", "true").lower() not in {
            "0", "false", "no", "off"
        }
        return endpoint, api_key, model, headers, verify_ssl

    @property
    def model_name(self) -> str:
        return self._configuration()[2]

    @staticmethod
    def _validate_vector(value: object) -> list[float]:
        if not isinstance(value, list) or not value:
            raise EmbeddingGatewayError("Embedding 服务返回了空向量")
        vector = [float(item) for item in value]
        if not all(math.isfinite(item) for item in vector):
            raise EmbeddingGatewayError("Embedding 服务返回了非有限数值")
        return vector

    async def _request_batch(
        self,
        endpoint: str,
        headers: dict[str, str],
        verify_ssl: bool,
        model: str,
        texts: list[str],
    ) -> list[list[float]]:
        verify: ssl.SSLContext | bool = (
            ssl.create_default_context(cafile=certifi.where()) if verify_ssl else False
        )
        try:
            async with httpx.AsyncClient(timeout=90, verify=verify) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json={"model": model, "input": texts, "encoding_format": "float"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingGatewayError(f"Embedding API 调用失败：{exc}") from exc
        items = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(items, list) or len(items) != len(texts):
            raise EmbeddingGatewayError("Embedding API 返回数量与输入数量不一致")
        ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
        return [self._validate_vector(item.get("embedding")) for item in ordered]

    async def embed(self, texts: list[str]) -> EmbeddingBatch:
        if not texts:
            raise EmbeddingGatewayError("Embedding 输入不能为空")
        endpoint, _api_key, model, headers, verify_ssl = self._configuration()
        cleaned = [text.strip() or "[empty]" for text in texts]
        vectors: list[list[float] | None] = [None] * len(cleaned)
        missing: list[tuple[int, str]] = []
        for index, text in enumerate(cleaned):
            cached = self.cache.get(model, text)
            if cached is None:
                missing.append((index, text))
            else:
                vectors[index] = cached
        started = time.perf_counter()
        api_calls = 0
        for offset in range(0, len(missing), 16):
            chunk = missing[offset : offset + 16]
            returned = await self._request_batch(
                endpoint, headers, verify_ssl, model, [item[1] for item in chunk]
            )
            api_calls += 1
            for (index, text), vector in zip(chunk, returned, strict=True):
                vectors[index] = vector
                self.cache.put(model, text, vector)
        completed = [item for item in vectors if item is not None]
        if len(completed) != len(cleaned):
            raise EmbeddingGatewayError("Embedding 结果组装失败")
        dimensions = {len(item) for item in completed}
        if len(dimensions) != 1:
            raise EmbeddingGatewayError("Embedding 向量维度不一致")
        return EmbeddingBatch(
            model=model,
            vectors=completed,
            dimension=dimensions.pop(),
            cache_hits=len(cleaned) - len(missing),
            api_calls=api_calls,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    async def test_connection(self) -> EmbeddingConnectionResult:
        try:
            batch = await self.embed(["SuYiTong embedding connectivity test"])
            return EmbeddingConnectionResult(
                ok=True,
                message="Embedding 服务连接正常",
                model=batch.model,
                dimension=batch.dimension,
                latency_ms=batch.latency_ms,
            )
        except EmbeddingGatewayError as exc:
            return EmbeddingConnectionResult(ok=False, message=str(exc))

