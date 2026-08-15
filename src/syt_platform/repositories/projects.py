"""SQLite 科研项目仓储。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from syt_platform.domain.project import (
    ProjectCreate,
    ResearchProject,
    ResearchStage,
    can_transition,
)


class ProjectNotFoundError(LookupError):
    pass


class InvalidStageTransitionError(ValueError):
    pass


class ProjectRepository:
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
                CREATE TABLE IF NOT EXISTS research_projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    research_direction TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ResearchProject:
        return ResearchProject.model_validate(dict(row))

    def create(self, request: ProjectCreate) -> ResearchProject:
        now = datetime.now(UTC)
        project = ResearchProject(
            id=str(uuid4()),
            title=request.title,
            research_direction=request.research_direction,
            mode=request.mode,
            stage=ResearchStage.INTAKE,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research_projects
                    (id, title, research_direction, mode, stage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.title,
                    project.research_direction,
                    project.mode.value,
                    project.stage.value,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
        return project

    def list(self) -> list[ResearchProject]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_projects ORDER BY created_at DESC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, project_id: str) -> ResearchProject:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id)
        return self._from_row(row)

    def transition(self, project_id: str, target: ResearchStage) -> ResearchProject:
        project = self.get(project_id)
        if not can_transition(project.stage, target):
            raise InvalidStageTransitionError(
                f"不能从 {project.stage.value} 跳转到 {target.value}"
            )
        updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE research_projects SET stage = ?, updated_at = ? WHERE id = ?",
                (target.value, updated_at.isoformat(), project_id),
            )
        return self.get(project_id)

    def enter_literature_review_from_confirmed_topic(
        self, project_id: str
    ) -> ResearchProject:
        """人工确认真实选题产物后进入文献调研；可修复旧原型产生的虚假阶段。"""

        self.get(project_id)
        updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE research_projects SET stage = ?, updated_at = ? WHERE id = ?",
                (ResearchStage.LITERATURE_REVIEW.value, updated_at.isoformat(), project_id),
            )
        return self.get(project_id)

    def enter_method_design_from_confirmed_literature(
        self, project_id: str
    ) -> ResearchProject:
        """文献综述产物通过人工确认后进入方法设计。"""

        self.get(project_id)
        updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE research_projects SET stage = ?, updated_at = ? WHERE id = ?",
                (ResearchStage.METHOD_DESIGN.value, updated_at.isoformat(), project_id),
            )
        return self.get(project_id)

    def enter_experiment_from_confirmed_method(self, project_id: str) -> ResearchProject:
        """方法设计产物通过人工确认后进入实验验证。"""

        self.get(project_id)
        updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE research_projects SET stage = ?, updated_at = ? WHERE id = ?",
                (ResearchStage.EXPERIMENT.value, updated_at.isoformat(), project_id),
            )
        return self.get(project_id)

    def enter_writing_from_confirmed_experiment(self, project_id: str) -> ResearchProject:
        """正式实验与结果审计通过后进入论文写作。"""

        self.get(project_id)
        updated_at = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "UPDATE research_projects SET stage = ?, updated_at = ? WHERE id = ?",
                (ResearchStage.WRITING.value, updated_at.isoformat(), project_id),
            )
        return self.get(project_id)
