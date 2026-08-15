"""B2/B3/PACM-SW 真实检索执行器与 JSONL 审计链路。"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Protocol
from uuid import uuid4

from syt_platform.domain.experiment import ExperimentRun
from syt_platform.domain.literature import LiteratureReviewRun, PaperRecord
from syt_platform.domain.method_design import MethodDesignRun
from syt_platform.domain.project import ResearchProject, ResearchStage
from syt_platform.domain.qrels import QrelsSet
from syt_platform.domain.retrieval import (
    RetrievalBenchmarkArtifact,
    RetrievalBenchmarkRun,
    RetrievalEngineCheck,
    RetrievalLogManifest,
    RetrievalQuerySummary,
    RetrievalRunRequest,
    RetrievalSystemResult,
)
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus
from syt_platform.repositories.retrieval_runs import RetrievalRunRepository
from syt_platform.services.embedding import EmbeddingBatch, EmbeddingGatewayError


SCHEMA_VERSION = "syt-retrieval-jsonl-v1"
SCORER_VERSION = "pacm-sw-retrieval-v1"
SYSTEMS = (
    ("B2", "Flat Vector RAG", "real_dense_embedding_retrieval"),
    ("B3", "Hybrid Retrieval", "real_bm25_dense_rrf"),
    ("Ours", "PACM-SW", "real_pacm_sw_four_layer_provenance_retrieval"),
)
ABLATION_SYSTEMS = (
    ("R1", "PACM-SW w/o Provenance Ranking", "real_pacm_sw_ablation_r1"),
    ("R2", "PACM-SW w/o Freshness", "real_pacm_sw_ablation_r2"),
    ("R3", "PACM-SW w/o Conflict Penalty", "real_pacm_sw_ablation_r3"),
    ("R4", "PACM-SW w/o Graph Connection", "real_pacm_sw_ablation_r4"),
    ("R5", "PACM-SW w/o Role Matching", "real_pacm_sw_ablation_r5"),
    ("R6", "PACM-SW w/o Provenance Contract", "real_pacm_sw_ablation_r6"),
)
ROLE_LAYER_WEIGHTS = {
    "researcher": {"semantic": 0.45, "procedural": 0.25, "episodic": 0.15, "constraint": 0.15},
    "planner": {"semantic": 0.25, "procedural": 0.35, "episodic": 0.15, "constraint": 0.25},
    "writer": {"semantic": 0.40, "procedural": 0.25, "episodic": 0.20, "constraint": 0.15},
    "reviewer": {"semantic": 0.30, "procedural": 0.20, "episodic": 0.15, "constraint": 0.35},
}
PACM_WEIGHTS = {
    "relevance": 0.55,
    "provenance": 0.15,
    "freshness": 0.08,
    "role": 0.08,
    "graph": 0.10,
    "conflict": -0.02,
    "redundancy": -0.04,
}


class RetrievalBenchmarkError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    async def embed(self, texts: list[str]) -> EmbeddingBatch: ...


@dataclass(frozen=True, slots=True)
class MemoryNode:
    id: str
    paper_id: str
    layer: str
    text: str
    provenance: dict[str, str | int | None]
    graph_links: frozenset[str]


@dataclass(slots=True)
class RankedCandidate:
    paper: PaperRecord
    final_score: float
    components: dict[str, float]
    memory_layers: list[str]
    graph_links: list[str]
    token_estimate: int
    selected: bool = False
    rank: int = 0


class JsonlAuditWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w", encoding="utf-8", newline="\n")
        self.record_count = 0

    def write(self, record: dict[str, object]) -> None:
        self.handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.record_count += 1

    def close(self) -> None:
        if not self.handle.closed:
            self.handle.close()


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9-]+|[\u4e00-\u9fff]", value.lower())


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise RetrievalBenchmarkError("查询与语料 Embedding 维度不一致")
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _minmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low, high = min(values.values()), max(values.values())
    if math.isclose(low, high):
        return {key: 1.0 if high > 0 else 0.0 for key in values}
    return {key: (value - low) / (high - low) for key, value in values.items()}


def _bm25(query: str, papers: list[PaperRecord], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    documents = {
        paper.id: _tokens(f"{paper.title} {paper.abstract}") for paper in papers
    }
    average_length = mean(len(tokens) for tokens in documents.values()) or 1.0
    document_frequency: Counter[str] = Counter()
    for tokens in documents.values():
        document_frequency.update(set(tokens))
    query_terms = _tokens(query)
    total = len(documents)
    scores: dict[str, float] = {}
    for paper_id, tokens in documents.items():
        counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            df = document_frequency[term]
            inverse = math.log(1 + (total - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1 - b + b * len(tokens) / average_length)
            score += inverse * frequency * (k1 + 1) / denominator
        scores[paper_id] = score
    return scores


def _provenance_completeness(paper: PaperRecord) -> float:
    fields = (paper.doi, paper.url, paper.abstract, paper.source_record_id, paper.source)
    return sum(bool(item) for item in fields) / len(fields)


def _token_estimate(paper: PaperRecord) -> int:
    return max(1, math.ceil(len(f"{paper.title}\n{paper.abstract}") / 4))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _tie_key(seed: int, paper_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{paper_id}".encode("utf-8")).hexdigest()


class RetrievalBenchmarkService:
    def __init__(
        self,
        repository: RetrievalRunRepository,
        embedding_gateway: EmbeddingProvider,
        data_dir: Path,
    ) -> None:
        self.repository = repository
        self.embedding_gateway = embedding_gateway
        self.data_dir = data_dir

    @staticmethod
    def _memory_nodes(
        literature: LiteratureReviewRun,
        method: MethodDesignRun,
    ) -> list[MemoryNode]:
        assert method.result is not None
        component_map: dict[str, list[str]] = {}
        for component in method.result.components:
            rendered = " ".join(
                [component.name, component.purpose, *component.algorithm_steps]
            )
            for paper_id in component.evidence_ids:
                component_map.setdefault(paper_id, []).append(
                    f"{component.id}:{rendered}"
                )
        design_map: dict[str, list[str]] = {}
        for index, link in enumerate(method.result.evidence_design_links, start=1):
            for paper_id in link.paper_ids:
                design_map.setdefault(paper_id, []).append(
                    f"design-{index}:{link.design_claim} {link.rationale}"
                )
        constraints = " ".join(
            [
                *method.result.provenance_contract.required_fields,
                *method.result.provenance_contract.invariants,
                *method.result.quality_gate_checklist,
            ]
        )
        nodes: list[MemoryNode] = []
        for paper in literature.papers:
            base_links = {
                f"query:{paper.matched_query.lower()}",
                f"source:{paper.source.lower()}",
            }
            if paper.doi:
                base_links.add(f"doi:{paper.doi.lower()}")
            for item in component_map.get(paper.id, []):
                base_links.add(f"component:{item.split(':', 1)[0]}")
            for item in design_map.get(paper.id, []):
                base_links.add(f"design:{item.split(':', 1)[0]}")
            provenance = {
                "paper_id": paper.id,
                "source": paper.source,
                "source_record_id": paper.source_record_id,
                "doi": paper.doi,
                "url": paper.url,
                "year": paper.year,
            }
            layer_texts = {
                "semantic": f"{paper.title}\n{paper.abstract}",
                "episodic": (
                    f"Retrieved for query: {paper.matched_query}. Source: {paper.source}. "
                    f"Year: {paper.year}. Venue: {paper.venue}. {paper.title}"
                ),
                "constraint": (
                    f"Evidence {paper.id}; DOI {paper.doi}; source record {paper.source_record_id}; "
                    f"required provenance constraints: {constraints}"
                ),
            }
            if component_map.get(paper.id) or design_map.get(paper.id):
                layer_texts["procedural"] = " ".join(
                    [*component_map.get(paper.id, []), *design_map.get(paper.id, [])]
                )
            for layer, text in layer_texts.items():
                nodes.append(
                    MemoryNode(
                        id=f"{paper.id}:{layer}",
                        paper_id=paper.id,
                        layer=layer,
                        text=text,
                        provenance=provenance,
                        graph_links=frozenset(base_links),
                    )
                )
        return nodes

    @staticmethod
    def _budget_select(
        ranked: list[RankedCandidate], top_k: int, budget: int
    ) -> list[RankedCandidate]:
        selected: list[RankedCandidate] = []
        used = 0
        for candidate in ranked:
            if len(selected) >= top_k:
                break
            if used + candidate.token_estimate > budget:
                continue
            candidate.selected = True
            candidate.rank = len(selected) + 1
            used += candidate.token_estimate
            selected.append(candidate)
        return selected

    @staticmethod
    def _metrics(
        query_run_id: str,
        query: str,
        role: str,
        seed: int,
        selected: list[RankedCandidate],
        relevant: set[str],
        latency_ms: float,
    ) -> RetrievalQuerySummary:
        ids = [item.paper.id for item in selected]
        hits = [index for index, paper_id in enumerate(ids, start=1) if paper_id in relevant]
        return RetrievalQuerySummary(
            query_run_id=query_run_id,
            query=query,
            role=role,
            seed=seed,
            selected_ids=ids,
            relevant_count=len(relevant),
            recall_at_k=round(len(hits) / len(relevant), 4) if relevant else 0.0,
            reciprocal_rank_at_k=round(1 / hits[0], 4) if hits else 0.0,
            provenance_coverage_at_k=round(
                mean(_provenance_completeness(item.paper) for item in selected), 4
            ) if selected else 0.0,
            context_tokens=sum(item.token_estimate for item in selected),
            latency_ms=round(latency_ms, 2),
        )

    @staticmethod
    def _candidate_record(candidate: RankedCandidate) -> dict[str, object]:
        return {
            "rank": candidate.rank,
            "paper_id": candidate.paper.id,
            "selected": candidate.selected,
            "final_score": round(candidate.final_score, 8),
            "score_components": {
                key: round(value, 8) for key, value in candidate.components.items()
            },
            "memory_layers": candidate.memory_layers,
            "graph_links": candidate.graph_links,
            "token_estimate": candidate.token_estimate,
            "provenance": {
                "doi": candidate.paper.doi,
                "url": candidate.paper.url,
                "source": candidate.paper.source,
                "source_record_id": candidate.paper.source_record_id,
                "year": candidate.paper.year,
            },
        }

    @staticmethod
    def _system_summary(
        system_id: str,
        name: str,
        level: str,
        queries: list[RetrievalQuerySummary],
    ) -> RetrievalSystemResult:
        return RetrievalSystemResult(
            system_id=system_id,
            system_name=name,
            implementation_level=level,
            scorer_version=SCORER_VERSION,
            query_results=queries,
            mean_recall_at_k=round(mean(item.recall_at_k for item in queries), 4),
            mean_mrr_at_k=round(mean(item.reciprocal_rank_at_k for item in queries), 4),
            mean_provenance_coverage_at_k=round(
                mean(item.provenance_coverage_at_k for item in queries), 4
            ),
            mean_context_tokens=round(mean(item.context_tokens for item in queries), 2),
            mean_latency_ms=round(mean(item.latency_ms for item in queries), 2),
        )

    @staticmethod
    def _flat_candidates(
        papers: list[PaperRecord],
        dense: dict[str, float],
        bm25: dict[str, float] | None,
        system_id: str,
        seed: int,
    ) -> list[RankedCandidate]:
        if system_id == "B2":
            final = dense
            components = {paper.id: {"dense_cosine": dense[paper.id]} for paper in papers}
        else:
            lexical = bm25 or {paper.id: 0.0 for paper in papers}
            dense_rank = {
                paper_id: index
                for index, (paper_id, _score) in enumerate(
                    sorted(dense.items(), key=lambda item: (-item[1], item[0])), start=1
                )
            }
            lexical_rank = {
                paper_id: index
                for index, (paper_id, _score) in enumerate(
                    sorted(lexical.items(), key=lambda item: (-item[1], item[0])), start=1
                )
            }
            final = {
                paper.id: 1 / (60 + dense_rank[paper.id]) + 1 / (60 + lexical_rank[paper.id])
                for paper in papers
            }
            components = {
                paper.id: {
                    "dense_cosine": dense[paper.id],
                    "bm25": lexical[paper.id],
                    "rrf_k": 60.0,
                    "dense_rank": float(dense_rank[paper.id]),
                    "bm25_rank": float(lexical_rank[paper.id]),
                }
                for paper in papers
            }
        ranked = [
            RankedCandidate(
                paper=paper,
                final_score=final[paper.id],
                components=components[paper.id],
                memory_layers=["semantic"],
                graph_links=[],
                token_estimate=_token_estimate(paper),
            )
            for paper in papers
        ]
        return sorted(ranked, key=lambda item: (-item.final_score, _tie_key(seed, item.paper.id)))

    @staticmethod
    def _pacm_candidates(
        papers: list[PaperRecord],
        nodes: list[MemoryNode],
        node_vectors: dict[str, list[float]],
        query_vector: list[float],
        lexical_scores: dict[str, float],
        role: str,
        top_k: int,
        budget: int,
        seed: int,
        ablation_id: str | None = None,
    ) -> list[RankedCandidate]:
        by_paper: dict[str, list[MemoryNode]] = {}
        for node in nodes:
            by_paper.setdefault(node.paper_id, []).append(node)
        layer_weights = dict(ROLE_LAYER_WEIGHTS[role])
        score_weights = dict(PACM_WEIGHTS)
        if ablation_id == "R1":
            score_weights["provenance"] = 0.0
        elif ablation_id == "R2":
            score_weights["freshness"] = 0.0
        elif ablation_id == "R3":
            score_weights["conflict"] = 0.0
        elif ablation_id == "R4":
            score_weights["graph"] = 0.0
        elif ablation_id == "R5":
            score_weights["role"] = 0.0
            layer_weights = {layer: 0.25 for layer in layer_weights}
        elif ablation_id == "R6":
            score_weights["provenance"] = 0.0
        normalized_bm25 = _minmax(lexical_scores)
        current_year = max((paper.year or 0 for paper in papers), default=2026)
        static: dict[str, dict[str, float]] = {}
        links: dict[str, set[str]] = {}
        token_sets = {
            paper.id: set(_tokens(f"{paper.title} {paper.abstract}")) for paper in papers
        }
        for paper in papers:
            paper_nodes = [
                node for node in by_paper[paper.id]
                if not (ablation_id == "R6" and node.layer == "constraint")
            ]
            layer_scores = {
                layer: max(
                    (_cosine(query_vector, node_vectors[node.id]) for node in paper_nodes if node.layer == layer),
                    default=0.0,
                )
                for layer in layer_weights
            }
            dense_layered = sum(layer_weights[layer] * layer_scores[layer] for layer in layer_weights)
            role_match = sum(
                layer_weights[layer] for layer in layer_weights if any(node.layer == layer for node in paper_nodes)
            )
            provenance = _provenance_completeness(paper)
            freshness = max(0.0, 1 - (current_year - (paper.year or current_year)) / 10)
            graph_links = set().union(*(set(node.graph_links) for node in paper_nodes))
            links[paper.id] = graph_links
            graph_prior = min(1.0, len(graph_links) / 6)
            relevance = 0.72 * dense_layered + 0.28 * normalized_bm25[paper.id]
            static[paper.id] = {
                "dense_layered": dense_layered,
                "semantic_dense": layer_scores["semantic"],
                "procedural_dense": layer_scores["procedural"],
                "episodic_dense": layer_scores["episodic"],
                "constraint_dense": layer_scores["constraint"],
                "bm25_normalized": normalized_bm25[paper.id],
                "relevance": relevance,
                "provenance": provenance,
                "freshness": freshness,
                "role_match": role_match,
                "graph_prior": graph_prior,
                "ablation_active": float(int(ablation_id[1:])) if ablation_id else 0.0,
            }
        selected_ids: list[str] = []
        selected_tokens: list[set[str]] = []
        selected_links: set[str] = set()
        remaining = {paper.id for paper in papers}
        ranked_selected: list[RankedCandidate] = []
        used = 0
        while remaining and len(ranked_selected) < top_k:
            round_candidates: list[RankedCandidate] = []
            for paper in papers:
                if paper.id not in remaining:
                    continue
                graph_connection = (
                    _jaccard(links[paper.id], selected_links)
                    if selected_links
                    else static[paper.id]["graph_prior"] * 0.25
                )
                redundancy = max(
                    (_jaccard(token_sets[paper.id], other) for other in selected_tokens),
                    default=0.0,
                )
                has_negation = bool(
                    set(_tokens(f"{paper.title} {paper.abstract}"))
                    & {"not", "no", "without", "fails", "failure", "不足", "无", "未"}
                )
                conflict = 0.0
                if selected_ids and has_negation:
                    conflict = max(
                        (_jaccard(token_sets[paper.id], other) for other in selected_tokens),
                        default=0.0,
                    )
                components = {
                    **static[paper.id],
                    "graph_connection": graph_connection,
                    "conflict_penalty": conflict,
                    "redundancy_penalty": redundancy,
                }
                score = (
                    score_weights["relevance"] * components["relevance"]
                    + score_weights["provenance"] * components["provenance"]
                    + score_weights["freshness"] * components["freshness"]
                    + score_weights["role"] * components["role_match"]
                    + score_weights["graph"] * components["graph_connection"]
                    + score_weights["conflict"] * components["conflict_penalty"]
                    + score_weights["redundancy"] * components["redundancy_penalty"]
                )
                round_candidates.append(
                    RankedCandidate(
                        paper=paper,
                        final_score=score,
                        components=components,
                        memory_layers=sorted({node.layer for node in by_paper[paper.id]}),
                        graph_links=sorted(links[paper.id]),
                        token_estimate=_token_estimate(paper),
                    )
                )
            round_candidates.sort(key=lambda item: (-item.final_score, _tie_key(seed, item.paper.id)))
            chosen = next(
                (item for item in round_candidates if used + item.token_estimate <= budget),
                None,
            )
            if chosen is None:
                break
            chosen.selected = True
            chosen.rank = len(ranked_selected) + 1
            ranked_selected.append(chosen)
            used += chosen.token_estimate
            remaining.remove(chosen.paper.id)
            selected_ids.append(chosen.paper.id)
            selected_tokens.append(token_sets[chosen.paper.id])
            selected_links.update(links[chosen.paper.id])
        selected_map = {item.paper.id: item for item in ranked_selected}
        final_candidates = ranked_selected[:]
        for paper in papers:
            if paper.id in selected_map:
                continue
            graph_connection = _jaccard(links[paper.id], selected_links) if selected_links else 0.0
            redundancy = max(
                (_jaccard(token_sets[paper.id], other) for other in selected_tokens), default=0.0
            )
            components = {
                **static[paper.id],
                "graph_connection": graph_connection,
                "conflict_penalty": 0.0,
                "redundancy_penalty": redundancy,
            }
            score = (
                score_weights["relevance"] * components["relevance"]
                + score_weights["provenance"] * components["provenance"]
                + score_weights["freshness"] * components["freshness"]
                + score_weights["role"] * components["role_match"]
                + score_weights["graph"] * components["graph_connection"]
                + score_weights["redundancy"] * components["redundancy_penalty"]
            )
            final_candidates.append(
                RankedCandidate(
                    paper=paper,
                    final_score=score,
                    components=components,
                    memory_layers=sorted({node.layer for node in by_paper[paper.id]}),
                    graph_links=sorted(links[paper.id]),
                    token_estimate=_token_estimate(paper),
                )
            )
        return final_candidates

    async def run(
        self,
        project: ResearchProject,
        experiment: ExperimentRun,
        method: MethodDesignRun,
        literature: LiteratureReviewRun,
        request: RetrievalRunRequest,
        qrels: QrelsSet | None = None,
    ) -> RetrievalBenchmarkRun:
        if project.stage != ResearchStage.EXPERIMENT:
            raise RetrievalBenchmarkError("项目尚未处于实验验证阶段")
        if experiment.status != RunStatus.COMPLETED or experiment.result is None:
            raise RetrievalBenchmarkError("缺少已完成的实验协议")
        if method.status != RunStatus.COMPLETED or method.result is None or method.confirmed_at is None:
            raise RetrievalBenchmarkError("METHOD 质量门尚未确认")
        if literature.status != RunStatus.COMPLETED or literature.result is None:
            raise RetrievalBenchmarkError("缺少已完成的文献集合")
        if request.evaluation_mode == "formal" and (qrels is None or qrels.status != "frozen"):
            raise RetrievalBenchmarkError("formal 检索批量运行前必须完成人工 qrels 并冻结")
        if qrels is not None and qrels.literature_run_id != literature.id:
            raise RetrievalBenchmarkError("qrels 与当前冻结文献运行不一致")
        try:
            embedding_model = self.embedding_gateway.model_name
        except EmbeddingGatewayError as exc:
            raise RetrievalBenchmarkError(str(exc)) from exc
        trace = [
            ExecutionStep(
                step="freeze_retrieval_inputs",
                status="completed",
                detail=f"冻结协议 {experiment.id}、方法 {method.id}、文献 {literature.id}、qrels {qrels.id if qrels else 'engineering-only'}",
            ),
            ExecutionStep(
                step="build_four_layer_memory",
                status="running",
                detail="构建 semantic / episodic / procedural / constraint 记忆节点",
            ),
        ]
        run = self.repository.create(
            project.id,
            experiment.id,
            method.id,
            literature.id,
            embedding_model,
            SCORER_VERSION,
            request,
            trace,
        )
        relative_path = Path("experiments") / project.id / run.id / "retrieval.jsonl"
        log_path = self.data_dir / relative_path
        writer = JsonlAuditWriter(log_path)
        try:
            nodes = self._memory_nodes(literature, method)
            layer_counts = Counter(node.layer for node in nodes)
            missing_layers = {"semantic", "episodic", "procedural", "constraint"} - set(layer_counts)
            if missing_layers:
                raise RetrievalBenchmarkError(
                    f"四层记忆构建不完整：缺少 {', '.join(sorted(missing_layers))}"
                )
            trace[1] = ExecutionStep(
                step="build_four_layer_memory",
                status="completed",
                detail="，".join(f"{key}={layer_counts[key]}" for key in sorted(layer_counts)),
            )
            active_systems = SYSTEMS + (ABLATION_SYSTEMS if request.include_ablations else ())
            writer.write(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "run_header",
                    "run_id": run.id,
                    "project_id": project.id,
                    "experiment_run_id": experiment.id,
                    "method_run_id": method.id,
                    "literature_run_id": literature.id,
                    "embedding_model": embedding_model,
                    "scorer_version": SCORER_VERSION,
                    "request": request.model_dump(mode="json"),
                    "systems": [item[0] for item in active_systems],
                    "seeds": request.seeds,
                    "qrels_set_id": qrels.id if qrels else None,
                    "qrels_sha256": qrels.frozen_sha256 if qrels else None,
                    "pacm_weights": PACM_WEIGHTS,
                    "role_layer_weights": ROLE_LAYER_WEIGHTS[request.role],
                    "memory_layer_counts": dict(layer_counts),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            trace.append(
                ExecutionStep(
                    step="external_embedding",
                    status="running",
                    detail=f"调用 {embedding_model} 生成真实语义向量",
                )
            )
            texts = [node.text for node in nodes] + list(literature.queries)
            batch = await self.embedding_gateway.embed(texts)
            node_vectors = {
                node.id: batch.vectors[index] for index, node in enumerate(nodes)
            }
            query_vectors = {
                query: batch.vectors[len(nodes) + index]
                for index, query in enumerate(literature.queries)
            }
            trace[-1] = ExecutionStep(
                step="external_embedding",
                status="completed",
                detail=(
                    f"model={batch.model} dim={batch.dimension} cache_hits={batch.cache_hits} "
                    f"api_calls={batch.api_calls} latency_ms={batch.latency_ms}"
                ),
            )
            semantic_vectors = {
                node.paper_id: node_vectors[node.id] for node in nodes if node.layer == "semantic"
            }
            trace.append(
                ExecutionStep(
                    step="execute_real_retrievers",
                    status="running",
                    detail="执行 B2 dense、B3 BM25+dense RRF、PACM-SW 四层溯源检索",
                )
            )
            system_results: list[RetrievalSystemResult] = []
            frozen_relevance: dict[str, set[str]] = {}
            if qrels is not None and qrels.status == "frozen":
                for item in qrels.items:
                    if item.judgment and item.judgment.relevance >= 2:
                        frozen_relevance.setdefault(item.query, set()).add(item.paper_id)
            for system_id, name, level in active_systems:
                summaries: list[RetrievalQuerySummary] = []
                for seed in request.seeds:
                    for query in literature.queries:
                        started = time.perf_counter()
                        dense = {
                            paper.id: _cosine(query_vectors[query], semantic_vectors[paper.id])
                            for paper in literature.papers
                        }
                        lexical = _bm25(query, literature.papers)
                        if system_id in {"B2", "B3"}:
                            candidates = self._flat_candidates(
                                literature.papers,
                                dense,
                                lexical if system_id == "B3" else None,
                                system_id,
                                seed,
                            )
                            selected = self._budget_select(
                                candidates, request.top_k, request.context_budget_tokens
                            )
                        else:
                            candidates = self._pacm_candidates(
                                literature.papers,
                                nodes,
                                node_vectors,
                                query_vectors[query],
                                lexical,
                                request.role,
                                request.top_k,
                                request.context_budget_tokens,
                                seed,
                                system_id if system_id.startswith("R") else None,
                            )
                            selected = [item for item in candidates if item.selected]
                        latency_ms = (time.perf_counter() - started) * 1000
                        if frozen_relevance:
                            relevant = frozen_relevance.get(query, set())
                            qrels_source = f"human_frozen:{qrels.id}:{qrels.frozen_sha256}"
                        else:
                            relevant = {
                                paper.id
                                for paper in literature.papers
                                if paper.matched_query.strip().lower() == query.strip().lower()
                            }
                            qrels_source = "literature.matched_query_engineering_only"
                        query_run_id = str(uuid4())
                        summary = self._metrics(
                            query_run_id,
                            query,
                            request.role,
                            seed,
                            selected,
                            relevant,
                            latency_ms,
                        )
                        summaries.append(summary)
                        writer.write(
                            {
                                "schema_version": SCHEMA_VERSION,
                                "record_type": "query_execution",
                                "run_id": run.id,
                                "query_run_id": query_run_id,
                                "system_id": system_id,
                                "system_name": name,
                                "implementation_level": level,
                                "ablation_id": system_id if system_id.startswith("R") else None,
                                "query": query,
                                "role": request.role,
                                "seed": seed,
                                "seed_scope": "deterministic_tie_break_only",
                                "top_k": request.top_k,
                                "context_budget_tokens": request.context_budget_tokens,
                                "corpus_size": len(literature.papers),
                                "qrels_source": qrels_source,
                                "relevant_ids": sorted(relevant),
                                "selected_ids": summary.selected_ids,
                                "metrics": summary.model_dump(mode="json"),
                                "candidates": [self._candidate_record(item) for item in candidates],
                                "status": "completed",
                                "created_at": datetime.now(UTC).isoformat(),
                            }
                        )
                system_results.append(self._system_summary(system_id, name, level, summaries))
            trace[-1] = ExecutionStep(
                step="execute_real_retrievers",
                status="completed",
                detail=f"完成 {len(active_systems)} 个配置 × {len(literature.queries)} 条查询 × {len(request.seeds)} seeds",
            )
            writer.write(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "run_footer",
                    "run_id": run.id,
                    "status": "completed",
                    "system_summaries": [item.model_dump(mode="json") for item in system_results],
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            )
            writer.close()
            sha256 = hashlib.sha256(log_path.read_bytes()).hexdigest()
            manifest = RetrievalLogManifest(
                schema_version=SCHEMA_VERSION,
                relative_path=relative_path.as_posix(),
                sha256=sha256,
                record_count=writer.record_count,
                embedding_model=batch.model,
                embedding_dimension=batch.dimension,
                corpus_size=len(literature.papers),
            )
            checks = [
                RetrievalEngineCheck(
                    id="RE-01",
                    name="真实 Embedding",
                    status="pass",
                    detail=f"{batch.model} / {batch.dimension} 维；API calls={batch.api_calls}，cache={batch.cache_hits}",
                ),
                RetrievalEngineCheck(
                    id="RE-02", name="B2 Flat Vector", status="pass",
                    detail="逐文献语义向量与查询向量使用 cosine 排序",
                ),
                RetrievalEngineCheck(
                    id="RE-03", name="B3 Hybrid", status="pass",
                    detail="BM25(k1=1.5,b=0.75) 与 dense rank 使用 RRF(k=60) 融合",
                ),
                RetrievalEngineCheck(
                    id="RE-04", name="PACM-SW", status="pass",
                    detail=f"四层节点 {dict(layer_counts)}；启用 provenance/role/graph/conflict/redundancy/budget",
                ),
                RetrievalEngineCheck(
                    id="RE-05", name="JSONL 完整性", status="pass",
                    detail=f"{writer.record_count} records / sha256 {sha256[:16]}…",
                ),
                RetrievalEngineCheck(
                    id="RE-06", name="R1-R6 消融",
                    status="pass" if request.include_ablations else "block",
                    detail="已执行六组单变量消融" if request.include_ablations else "本轮未启用六组消融",
                ),
                RetrievalEngineCheck(
                    id="RE-07", name="三随机种子批量",
                    status="pass" if len(request.seeds) >= 3 else "block",
                    detail=f"seeds={request.seeds}；检索确定性，seed 仅用于同分排序",
                ),
                RetrievalEngineCheck(
                    id="RE-08", name="独立人工 qrels",
                    status="pass" if qrels is not None and qrels.status == "frozen" else "block",
                    detail=(f"qrels={qrels.id} sha256={qrels.frozen_sha256}" if qrels and qrels.status == "frozen" else "当前仍使用 matched_query 工程标签"),
                ),
                RetrievalEngineCheck(
                    id="RE-09", name="正式论文效果门", status="block",
                    detail="仍需 B0/B1 与检索增强生成系统同任务对比、人工写作质量评审和统计审计",
                ),
            ]
            trace.append(
                ExecutionStep(
                    step="seal_jsonl_manifest",
                    status="completed",
                    detail=f"records={writer.record_count} sha256={sha256}",
                )
            )
            artifact = RetrievalBenchmarkArtifact(
                systems=system_results,
                engine_checks=checks,
                log_manifest=manifest,
                validation_level=("human_qrels_ablation_three_seed_retrieval" if qrels and qrels.status == "frozen" and request.include_ablations and len(request.seeds) >= 3 else "real_retrieval_engine_engineering_validation"),
                benchmark_status=("retrieval_batch_complete_generation_comparison_pending" if qrels and qrels.status == "frozen" and request.include_ablations and len(request.seeds) >= 3 else "retrieval_engines_implemented_formal_benchmark_pending"),
                efficacy_claim_allowed=False,
                blockers=["仍需 B0/B1 与检索增强生成系统同任务对比、人工写作质量评审和统计审计"],
                limitations=[
                    "Embedding、BM25、RRF 与 PACM-SW 评分均由真实执行器运行，不再使用元数据 proxy。",
                    ("指标使用已冻结的独立人工 qrels。" if qrels and qrels.status == "frozen" else "当前相关集合仍由 literature.matched_query 构造，只能用于工程验证。"),
                    "PACM-SW procedural 节点只覆盖 METHOD 中存在 evidence link 的论文。",
                    "冲突检测当前为可审计的词项启发式，正式实验前需替换为冻结的 claim-level 检测器。",
                    "检索执行器是确定性的；三个 seed 只验证同分排序稳定性，不产生伪随机重复样本。",
                    "本轮只比较检索层，不能推导整篇论文生成质量或方法总体有效性。",
                ],
            )
            return self.repository.complete(run.id, artifact, trace)
        except (EmbeddingGatewayError, RetrievalBenchmarkError, ValueError) as exc:
            writer.write(
                {
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "run_error",
                    "run_id": run.id,
                    "status": "failed",
                    "error": str(exc)[:1000],
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            writer.close()
            failed_index = next(
                (index for index, item in enumerate(trace) if item.status == "running"),
                len(trace) - 1,
            )
            trace[failed_index] = trace[failed_index].model_copy(
                update={"status": "failed", "detail": str(exc)[:300]}
            )
            self.repository.fail(run.id, str(exc), trace)
            raise RetrievalBenchmarkError(str(exc)) from exc
