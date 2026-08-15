"""选题拆解运行记录与产物仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.topic_framing import (
    ContextItem,
    ExecutionStep,
    RunStatus,
    TopicFramingResult,
    TopicFramingRun,
    TopicGateDecision,
)


class TopicRunNotFoundError(LookupError):
    pass


class TopicRunRepository:
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
                CREATE TABLE IF NOT EXISTS topic_framing_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    input_contexts_json TEXT NOT NULL,
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
                "CREATE INDEX IF NOT EXISTS idx_topic_runs_project_created "
                "ON topic_framing_runs(project_id, created_at DESC)"
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
    def _from_row(row: sqlite3.Row) -> TopicFramingRun:
        raw = dict(row)
        raw["input_contexts"] = json.loads(raw.pop("input_contexts_json"))
        raw["execution_trace"] = json.loads(raw.pop("execution_trace_json"))
        raw["result"] = json.loads(raw.pop("result_json")) if raw["result_json"] else None
        raw["decision"] = json.loads(raw.pop("decision_json")) if raw["decision_json"] else None
        return TopicFramingRun.model_validate(raw)

    def create(
        self,
        project_id: str,
        model_name: str,
        prompt_version: str,
        contexts: list[ContextItem],
        trace: list[ExecutionStep],
    ) -> TopicFramingRun:
        run_id = str(uuid4())
        created_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO topic_framing_runs
                    (id, project_id, status, model_name, prompt_version,
                     input_contexts_json, execution_trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    RunStatus.RUNNING.value,
                    model_name,
                    prompt_version,
                    self._dump(contexts),
                    self._dump(trace),
                    created_at.isoformat(),
                ),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> TopicFramingRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM topic_framing_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise TopicRunNotFoundError(run_id)
        return self._from_row(row)

    def latest(self, project_id: str) -> TopicFramingRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM topic_framing_runs WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def complete(
        self,
        run_id: str,
        result: TopicFramingResult,
        trace: list[ExecutionStep],
    ) -> TopicFramingRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE topic_framing_runs
                SET status = ?, result_json = ?, execution_trace_json = ?,
                    completed_at = ?, error = NULL
                WHERE id = ?
                """,
                (
                    RunStatus.COMPLETED.value,
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
        trace: list[ExecutionStep],
    ) -> TopicFramingRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE topic_framing_runs
                SET status = ?, error = ?, execution_trace_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    RunStatus.FAILED.value,
                    error[:1000],
                    self._dump(trace),
                    completed_at.isoformat(),
                    run_id,
                ),
            )
        return self.get(run_id)

    def confirm(self, run_id: str, decision: TopicGateDecision) -> TopicFramingRun:
        confirmed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE topic_framing_runs
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
