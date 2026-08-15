"""人工 qrels 集合仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.qrels import QrelsPoolItem, QrelsSet


class QrelsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS qrels_sets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    literature_run_id TEXT NOT NULL,
                    retrieval_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pool_depth INTEGER NOT NULL,
                    assessor_id TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    items_json TEXT NOT NULL,
                    query_count INTEGER NOT NULL,
                    judgment_count INTEGER NOT NULL,
                    frozen_sha256 TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    frozen_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_qrels_project_created "
                "ON qrels_sets(project_id, created_at DESC)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump_items(items: list[QrelsPoolItem]) -> str:
        return json.dumps(
            [item.model_dump(mode="json") for item in items], ensure_ascii=False
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> QrelsSet:
        raw = dict(row)
        raw["items"] = json.loads(raw.pop("items_json"))
        return QrelsSet.model_validate(raw)

    def create(
        self,
        project_id: str,
        literature_run_id: str,
        retrieval_run_id: str,
        pool_depth: int,
        assessor_id: str,
        instructions: str,
        items: list[QrelsPoolItem],
    ) -> QrelsSet:
        set_id = str(uuid4())
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO qrels_sets
                    (id, project_id, literature_run_id, retrieval_run_id, status,
                     pool_depth, assessor_id, instructions, items_json, query_count,
                     judgment_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    set_id,
                    project_id,
                    literature_run_id,
                    retrieval_run_id,
                    pool_depth,
                    assessor_id,
                    instructions,
                    self._dump_items(items),
                    len({item.query for item in items}),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.get(set_id)

    def get(self, set_id: str) -> QrelsSet:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM qrels_sets WHERE id = ?", (set_id,)
            ).fetchone()
        if row is None:
            raise LookupError(set_id)
        return self._from_row(row)

    def latest(self, project_id: str) -> QrelsSet | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM qrels_sets WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def save_items(self, set_id: str, items: list[QrelsPoolItem]) -> QrelsSet:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE qrels_sets
                SET items_json = ?, judgment_count = ?, updated_at = ?
                WHERE id = ? AND status = 'draft'
                """,
                (
                    self._dump_items(items),
                    sum(item.judgment is not None for item in items),
                    now.isoformat(),
                    set_id,
                ),
            )
        return self.get(set_id)

    def freeze(self, set_id: str, sha256: str) -> QrelsSet:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE qrels_sets
                SET status = 'frozen', frozen_sha256 = ?, frozen_at = ?, updated_at = ?
                WHERE id = ? AND status = 'draft'
                """,
                (sha256, now.isoformat(), now.isoformat(), set_id),
            )
        return self.get(set_id)

