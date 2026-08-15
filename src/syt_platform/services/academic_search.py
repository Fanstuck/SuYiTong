"""OpenAlex 与 Crossref 双源学术元数据检索。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from syt_platform.domain.literature import PaperRecord
from syt_platform.services.jiuwenswarm import _dotenv_keys


class AcademicSearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AcademicSourceConnectionResult:
    ok: bool
    provider: str
    message: str
    status_code: int | None = None
    daily_limit: int | None = None
    remaining: int | None = None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", text).strip()


def _openalex_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        positions.extend((offset, word) for offset in offsets)
    return " ".join(word for _, word in sorted(positions))


def _normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    return value.lower().replace("https://doi.org/", "").replace("http://doi.org/", "").strip()


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


_DOMAIN_ANCHORS = {
    "agent",
    "agents",
    "agentic",
    "llm",
    "language model",
    "retrieval",
    "rag",
    "memory",
    "context",
    "provenance",
    "multi-agent",
    "scientific writing",
}


def _lexical_relevance(record: dict[str, Any]) -> float:
    haystack = f"{record.get('title', '')} {record.get('abstract', '')}".lower()
    query_terms = {
        term
        for term in re.findall(r"[a-z][a-z0-9-]{2,}", str(record.get("matched_query", "")).lower())
        if term not in {"the", "for", "and", "with", "from", "aware", "based"}
    }
    overlap = sum(1 for term in query_terms if term in haystack)
    anchors = sum(1 for anchor in _DOMAIN_ANCHORS if anchor in haystack)
    title = str(record.get("title", "")).lower()
    title_anchors = sum(1 for anchor in _DOMAIN_ANCHORS if anchor in title)
    return overlap * 8 + anchors * 3 + title_anchors * 10


class AcademicSearchService:
    OPENALEX_URL = "https://api.openalex.org/works"
    CROSSREF_URL = "https://api.crossref.org/works"

    def __init__(self, environment_path: Path | None = None) -> None:
        self.environment_path = environment_path

    def _openalex_api_key(self) -> str:
        if self.environment_path is None:
            return ""
        return _dotenv_keys(self.environment_path).get("OPENALEX_API_KEY", "").strip()

    def _openalex_headers(self) -> dict[str, str]:
        api_key = self._openalex_api_key()
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def test_openalex_connection(self) -> AcademicSourceConnectionResult:
        api_key = self._openalex_api_key()
        if not api_key:
            return AcademicSourceConnectionResult(
                False,
                "OpenAlex",
                "请先保存 OpenAlex API Key",
            )
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(
                    self.OPENALEX_URL,
                    params={"search": "agent memory", "per_page": 1, "select": "id,title"},
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "User-Agent": "SuYiTong/0.1 academic-research-platform",
                    },
                )
            if response.is_success:
                return AcademicSourceConnectionResult(
                    True,
                    "OpenAlex",
                    "OpenAlex 认证检索连接成功",
                    response.status_code,
                    _optional_int(response.headers.get("X-RateLimit-Limit")),
                    _optional_int(response.headers.get("X-RateLimit-Remaining")),
                )
            return AcademicSourceConnectionResult(
                False,
                "OpenAlex",
                f"OpenAlex 返回 HTTP {response.status_code}",
                response.status_code,
            )
        except httpx.HTTPError as exc:
            return AcademicSourceConnectionResult(
                False,
                "OpenAlex",
                f"OpenAlex 连接失败：{exc.__class__.__name__}",
            )

    async def search(self, queries: list[str], per_query: int = 6) -> list[PaperRecord]:
        limited_queries = [query.strip() for query in queries if query.strip()][:6]
        if not limited_queries:
            raise AcademicSearchError("选题产物中没有可用文献检索式")
        records: list[dict[str, Any]] = []
        errors: list[str] = []
        headers = {
            "User-Agent": "SuYiTong/0.1 academic-research-platform",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(
            timeout=25,
            follow_redirects=True,
            headers=headers,
        ) as client:
            for query in limited_queries:
                try:
                    records.extend(await self._search_openalex(client, query, per_query))
                except httpx.HTTPError as exc:
                    errors.append(f"OpenAlex:{exc.__class__.__name__}")
                try:
                    records.extend(await self._search_crossref(client, query, per_query))
                except httpx.HTTPError as exc:
                    errors.append(f"Crossref:{exc.__class__.__name__}")
        papers = self._deduplicate(records)
        if not papers:
            raise AcademicSearchError("学术元数据检索没有返回记录；" + ", ".join(errors[:4]))
        return papers[:30]

    async def _search_openalex(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_query: int,
    ) -> list[dict[str, Any]]:
        response = await client.get(
            self.OPENALEX_URL,
            params={"search": query, "per_page": per_query},
            headers=self._openalex_headers(),
        )
        response.raise_for_status()
        records: list[dict[str, Any]] = []
        for item in response.json().get("results", []):
            location = item.get("primary_location") or {}
            source = location.get("source") or {}
            authors = [
                (authorship.get("author") or {}).get("display_name", "")
                for authorship in item.get("authorships") or []
            ]
            records.append(
                {
                    "title": item.get("display_name") or item.get("title") or "",
                    "authors": [author for author in authors if author],
                    "year": item.get("publication_year"),
                    "venue": source.get("display_name") or "",
                    "doi": _normalize_doi(item.get("doi")),
                    "url": (item.get("open_access") or {}).get("oa_url")
                    or location.get("landing_page_url")
                    or item.get("id")
                    or "",
                    "abstract": _openalex_abstract(item.get("abstract_inverted_index")),
                    "cited_by_count": item.get("cited_by_count") or 0,
                    "source": "OpenAlex",
                    "source_record_id": item.get("id") or "",
                    "matched_query": query,
                    "relevance_score": float(item.get("relevance_score") or 0),
                }
            )
        return records

    async def _search_crossref(
        self,
        client: httpx.AsyncClient,
        query: str,
        per_query: int,
    ) -> list[dict[str, Any]]:
        response = await client.get(
            self.CROSSREF_URL,
            params={
                "query.bibliographic": query,
                "rows": per_query,
                "select": (
                    "DOI,title,author,published,container-title,URL,abstract,"
                    "is-referenced-by-count,score"
                ),
            },
        )
        response.raise_for_status()
        records: list[dict[str, Any]] = []
        for item in (response.json().get("message") or {}).get("items", []):
            date_parts = ((item.get("published") or {}).get("date-parts") or [[]])[0]
            authors = [
                " ".join(filter(None, [author.get("given"), author.get("family")]))
                for author in item.get("author") or []
            ]
            records.append(
                {
                    "title": (item.get("title") or [""])[0],
                    "authors": [author for author in authors if author],
                    "year": date_parts[0] if date_parts else None,
                    "venue": (item.get("container-title") or [""])[0],
                    "doi": _normalize_doi(item.get("DOI")),
                    "url": item.get("URL") or "",
                    "abstract": _clean_text(item.get("abstract")),
                    "cited_by_count": item.get("is-referenced-by-count") or 0,
                    "source": "Crossref",
                    "source_record_id": item.get("DOI") or item.get("URL") or "",
                    "matched_query": query,
                    "relevance_score": float(item.get("score") or 0),
                }
            )
        return records

    @staticmethod
    def _deduplicate(records: list[dict[str, Any]]) -> list[PaperRecord]:
        merged: dict[str, dict[str, Any]] = {}
        for record in records:
            title = _clean_text(record.get("title"))
            if not title:
                continue
            doi = _normalize_doi(record.get("doi"))
            key = f"doi:{doi}" if doi else f"title:{_title_key(title)}"
            if len(key) < 12:
                continue
            record["title"] = title
            record["doi"] = doi
            record["lexical_relevance"] = _lexical_relevance(record)
            existing = merged.get(key)
            if existing is None:
                merged[key] = record
                continue
            if not existing.get("abstract") and record.get("abstract"):
                existing["abstract"] = record["abstract"]
            if not existing.get("url") and record.get("url"):
                existing["url"] = record["url"]
            if len(record.get("authors") or []) > len(existing.get("authors") or []):
                existing["authors"] = record["authors"]
            existing["cited_by_count"] = max(
                existing.get("cited_by_count") or 0,
                record.get("cited_by_count") or 0,
            )
            existing["lexical_relevance"] = max(
                existing.get("lexical_relevance") or 0,
                record.get("lexical_relevance") or 0,
            )
            existing["source"] = "+".join(
                sorted(set(existing["source"].split("+")) | {record["source"]})
            )
        ranked = sorted(
            merged.values(),
            key=lambda item: (
                item.get("lexical_relevance") or 0,
                bool(item.get("abstract")),
                item.get("relevance_score") or 0,
                min(item.get("cited_by_count") or 0, 500),
            ),
            reverse=True,
        )
        return [
            PaperRecord(
                id=f"PAPER-{index:03d}",
                **{key: value for key, value in record.items() if key != "lexical_relevance"},
            )
            for index, record in enumerate(ranked, start=1)
        ]


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None
