"""从真实检索候选池生成盲化人工 qrels，并执行冻结质量门。"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from syt_platform.domain.literature import LiteratureReviewRun
from syt_platform.domain.qrels import (
    QrelJudgment,
    QrelsCreateRequest,
    QrelsJudgmentBatch,
    QrelsPoolItem,
    QrelsSet,
)
from syt_platform.domain.retrieval import RetrievalBenchmarkRun
from syt_platform.repositories.qrels import QrelsRepository


class QrelsError(RuntimeError):
    pass


DEFAULT_INSTRUCTIONS = (
    "请仅依据查询与论文题名/摘要判断，不参考系统排名。0=不相关，1=弱相关，"
    "2=相关，3=高度相关。无法判断时先保留未标注，不得由模型自动代填。"
)


class QrelsService:
    def __init__(self, repository: QrelsRepository, data_dir: Path) -> None:
        self.repository = repository
        self.data_dir = data_dir

    def create_pool(
        self,
        project_id: str,
        literature: LiteratureReviewRun,
        retrieval: RetrievalBenchmarkRun,
        request: QrelsCreateRequest,
    ) -> QrelsSet:
        if retrieval.result is None:
            raise QrelsError("真实检索运行尚未完成")
        path = (self.data_dir / retrieval.result.log_manifest.relative_path).resolve()
        if not path.is_relative_to(self.data_dir.resolve()) or not path.is_file():
            raise QrelsError("真实检索 JSONL 不存在")
        pools: dict[str, set[str]] = {}
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("record_type") != "query_execution":
                    continue
                query = str(record["query"])
                candidate_ids = [
                    str(item["paper_id"])
                    for item in record.get("candidates", [])[: request.pool_depth]
                ]
                pools.setdefault(query, set()).update(candidate_ids)
        paper_map = {paper.id: paper for paper in literature.papers}
        items: list[QrelsPoolItem] = []
        for query, paper_ids in pools.items():
            # 哈希排序用于盲化原系统排名，同时保持池可复现。
            blinded = sorted(
                paper_ids,
                key=lambda paper_id: hashlib.sha256(
                    f"{query}\0{paper_id}\0qrels-blind-v1".encode("utf-8")
                ).hexdigest(),
            )
            for paper_id in blinded:
                paper = paper_map.get(paper_id)
                if paper is None:
                    continue
                items.append(
                    QrelsPoolItem(
                        query=query,
                        paper_id=paper.id,
                        title=paper.title,
                        abstract=paper.abstract,
                        year=paper.year,
                        doi=paper.doi,
                    )
                )
        if not items:
            raise QrelsError("候选池为空，无法创建 qrels")
        return self.repository.create(
            project_id,
            literature.id,
            retrieval.id,
            request.pool_depth,
            request.assessor_id.strip(),
            request.instructions.strip() or DEFAULT_INSTRUCTIONS,
            items,
        )

    def save_judgments(self, qrels: QrelsSet, request: QrelsJudgmentBatch) -> QrelsSet:
        if qrels.status != "draft":
            raise QrelsError("qrels 已冻结，不能继续修改")
        if request.assessor_id.strip() != qrels.assessor_id:
            raise QrelsError("标注者 ID 与 qrels 创建者不一致")
        keyed = {(item.query, item.paper_id): item for item in qrels.items}
        unknown = [
            item for item in request.judgments if (item.query, item.paper_id) not in keyed
        ]
        if unknown:
            raise QrelsError("提交中包含不属于盲化候选池的 query/paper")
        now = datetime.now(UTC)
        for submitted in request.judgments:
            key = (submitted.query, submitted.paper_id)
            keyed[key] = keyed[key].model_copy(
                update={
                    "judgment": QrelJudgment(
                        relevance=submitted.relevance,
                        rationale=submitted.rationale.strip(),
                        assessor_id=qrels.assessor_id,
                        judged_at=now,
                    )
                }
            )
        ordered = [keyed[(item.query, item.paper_id)] for item in qrels.items]
        return self.repository.save_items(qrels.id, ordered)

    def freeze(self, qrels: QrelsSet) -> QrelsSet:
        if qrels.status != "draft":
            raise QrelsError("qrels 已经冻结")
        missing = [item for item in qrels.items if item.judgment is None]
        if missing:
            raise QrelsError(f"仍有 {len(missing)} 个候选未完成人工标注")
        for query in {item.query for item in qrels.items}:
            relevant = [
                item for item in qrels.items
                if item.query == query and item.judgment and item.judgment.relevance >= 2
            ]
            if not relevant:
                raise QrelsError(f"查询“{query}”没有 grade>=2 的相关文献，请复核")
        payload = [
            {
                "query": item.query,
                "paper_id": item.paper_id,
                "relevance": item.judgment.relevance if item.judgment else None,
                "rationale": item.judgment.rationale if item.judgment else "",
                "assessor_id": item.judgment.assessor_id if item.judgment else "",
            }
            for item in sorted(qrels.items, key=lambda item: (item.query, item.paper_id))
        ]
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return self.repository.freeze(qrels.id, digest)

