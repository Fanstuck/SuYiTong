"""文献调研运行、论文元数据和综述产物仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.literature import (
    LiteratureGateDecision,
    LiteratureReviewRun,
    LiteratureSynthesis,
    PaperRecord,
)
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class LiteratureRunRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS literature_review_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    topic_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    queries_json TEXT NOT NULL,
                    papers_json TEXT NOT NULL,
                    execution_trace_json TEXT NOT NULL,
                    result_json TEXT,
                    decision_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    confirmed_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_literature_runs_project_created "
                "ON literature_review_runs(project_id, created_at DESC)"
            )

    @staticmethod
    def _dump(value: object) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif isinstance(value, (list, tuple)):
            value = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in value
            ]
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> LiteratureReviewRun:
        raw = dict(row)
        raw["queries"] = json.loads(raw.pop("queries_json"))
        raw["papers"] = json.loads(raw.pop("papers_json"))
        raw["execution_trace"] = json.loads(raw.pop("execution_trace_json"))
        raw["result"] = json.loads(raw.pop("result_json")) if raw["result_json"] else None
        raw["decision"] = json.loads(raw.pop("decision_json")) if raw["decision_json"] else None
        return LiteratureReviewRun.model_validate(raw)

    def create(
        self,
        project_id: str,
        topic_run_id: str,
        model_name: str,
        prompt_version: str,
        queries: list[str],
        trace: list[ExecutionStep],
    ) -> LiteratureReviewRun:
        run_id = str(uuid4())
        created_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO literature_review_runs
                    (id, project_id, topic_run_id, status, model_name, prompt_version,
                     queries_json, papers_json, execution_trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    topic_run_id,
                    RunStatus.RUNNING.value,
                    model_name,
                    prompt_version,
                    self._dump(queries),
                    "[]",
                    self._dump(trace),
                    created_at.isoformat(),
                ),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> LiteratureReviewRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM literature_review_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise LookupError(run_id)
        return self._from_row(row)

    def latest(self, project_id: str) -> LiteratureReviewRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM literature_review_runs WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def complete(
        self,
        run_id: str,
        papers: list[PaperRecord],
        result: LiteratureSynthesis,
        trace: list[ExecutionStep],
    ) -> LiteratureReviewRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE literature_review_runs
                SET status = ?, papers_json = ?, result_json = ?,
                    execution_trace_json = ?, completed_at = ?, error = NULL
                WHERE id = ?
                """,
                (
                    RunStatus.COMPLETED.value,
                    self._dump(papers),
                    self._dump(result),
                    self._dump(trace),
                    completed_at.isoformat(),
                    run_id,
                ),
            )
        return self.get(run_id)

    def fail(
        self,
        run_id: str,
        error: str,
        papers: list[PaperRecord],
        trace: list[ExecutionStep],
    ) -> LiteratureReviewRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE literature_review_runs
                SET status = ?, papers_json = ?, error = ?,
                    execution_trace_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    RunStatus.FAILED.value,
                    self._dump(papers),
                    error[:1200],
                    self._dump(trace),
                    completed_at.isoformat(),
                    run_id,
                ),
            )
        return self.get(run_id)

    def confirm(
        self, run_id: str, decision: LiteratureGateDecision
    ) -> LiteratureReviewRun:
        confirmed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE literature_review_runs
                SET decision_json = ?, confirmed_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    self._dump(decision),
                    confirmed_at.isoformat(),
                    run_id,
                    RunStatus.COMPLETED.value,
                ),
            )
        return self.get(run_id)
