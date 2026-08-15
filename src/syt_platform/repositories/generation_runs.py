"""B0/B1 生成批量运行仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.generation_benchmark import (
    GenerationBatchArtifact,
    GenerationBatchRequest,
    GenerationBatchRun,
)
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class GenerationRunRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_batch_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    experiment_run_id TEXT NOT NULL,
                    qrels_set_id TEXT,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    execution_trace_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_generation_runs_project_created "
                "ON generation_batch_runs(project_id, created_at DESC)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _dump(value: object) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        elif isinstance(value, list):
            value = [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in value]
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> GenerationBatchRun:
        raw = dict(row)
        raw["request"] = json.loads(raw.pop("request_json"))
        raw["execution_trace"] = json.loads(raw.pop("execution_trace_json"))
        raw["result"] = json.loads(raw.pop("result_json")) if raw["result_json"] else None
        return GenerationBatchRun.model_validate(raw)

    def create(
        self,
        project_id: str,
        experiment_run_id: str,
        qrels_set_id: str | None,
        model_name: str,
        request: GenerationBatchRequest,
        trace: list[ExecutionStep],
    ) -> GenerationBatchRun:
        run_id, now = str(uuid4()), datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_batch_runs
                    (id, project_id, experiment_run_id, qrels_set_id, status,
                     model_name, request_json, execution_trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, project_id, experiment_run_id, qrels_set_id,
                 RunStatus.RUNNING.value, model_name, self._dump(request),
                 self._dump(trace), now.isoformat()),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> GenerationBatchRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM generation_batch_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise LookupError(run_id)
        return self._from_row(row)

    def latest(self, project_id: str) -> GenerationBatchRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM generation_batch_runs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def complete(self, run_id: str, result: GenerationBatchArtifact, trace: list[ExecutionStep]) -> GenerationBatchRun:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE generation_batch_runs SET status=?, result_json=?, execution_trace_json=?, completed_at=?, error=NULL WHERE id=?",
                (RunStatus.COMPLETED.value, self._dump(result), self._dump(trace), now.isoformat(), run_id),
            )
        return self.get(run_id)

    def fail(self, run_id: str, error: str, trace: list[ExecutionStep]) -> GenerationBatchRun:
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE generation_batch_runs SET status=?, error=?, execution_trace_json=?, completed_at=? WHERE id=?",
                (RunStatus.FAILED.value, error[:1200], self._dump(trace), now.isoformat(), run_id),
            )
        return self.get(run_id)

