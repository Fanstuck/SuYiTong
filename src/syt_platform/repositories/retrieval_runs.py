"""真实检索 benchmark 运行仓储。"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.retrieval import (
    RetrievalBenchmarkArtifact,
    RetrievalBenchmarkRun,
    RetrievalRunRequest,
)
from syt_platform.domain.topic_framing import ExecutionStep, RunStatus


class RetrievalRunRepository:
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
                CREATE TABLE IF NOT EXISTS retrieval_benchmark_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    experiment_run_id TEXT NOT NULL,
                    method_run_id TEXT NOT NULL,
                    literature_run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    scorer_version TEXT NOT NULL,
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
                "CREATE INDEX IF NOT EXISTS idx_retrieval_runs_project_created "
                "ON retrieval_benchmark_runs(project_id, created_at DESC)"
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
    def _from_row(row: sqlite3.Row) -> RetrievalBenchmarkRun:
        raw = dict(row)
        raw["request"] = json.loads(raw.pop("request_json"))
        raw["execution_trace"] = json.loads(raw.pop("execution_trace_json"))
        raw["result"] = json.loads(raw.pop("result_json")) if raw["result_json"] else None
        return RetrievalBenchmarkRun.model_validate(raw)

    def create(
        self,
        project_id: str,
        experiment_run_id: str,
        method_run_id: str,
        literature_run_id: str,
        embedding_model: str,
        scorer_version: str,
        request: RetrievalRunRequest,
        trace: list[ExecutionStep],
    ) -> RetrievalBenchmarkRun:
        run_id = str(uuid4())
        created_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO retrieval_benchmark_runs
                    (id, project_id, experiment_run_id, method_run_id,
                     literature_run_id, status, embedding_model, scorer_version,
                     request_json, execution_trace_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    experiment_run_id,
                    method_run_id,
                    literature_run_id,
                    RunStatus.RUNNING.value,
                    embedding_model,
                    scorer_version,
                    self._dump(request),
                    self._dump(trace),
                    created_at.isoformat(),
                ),
            )
        return self.get(run_id)

    def get(self, run_id: str) -> RetrievalBenchmarkRun:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM retrieval_benchmark_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise LookupError(run_id)
        return self._from_row(row)

    def latest(self, project_id: str) -> RetrievalBenchmarkRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM retrieval_benchmark_runs WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def complete(
        self,
        run_id: str,
        result: RetrievalBenchmarkArtifact,
        trace: list[ExecutionStep],
    ) -> RetrievalBenchmarkRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE retrieval_benchmark_runs
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

    def fail(self, run_id: str, error: str, trace: list[ExecutionStep]) -> RetrievalBenchmarkRun:
        completed_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE retrieval_benchmark_runs
                SET status = ?, error = ?, execution_trace_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    RunStatus.FAILED.value,
                    error[:1200],
                    self._dump(trace),
                    completed_at.isoformat(),
                    run_id,
                ),
            )
        return self.get(run_id)

