from pathlib import Path

import pytest

from syt_platform.domain.project import ProjectCreate, ResearchStage
from syt_platform.repositories.projects import InvalidStageTransitionError, ProjectRepository


def test_project_must_advance_one_quality_gate_at_a_time(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path / "test.db")
    project = repository.create(
        ProjectCreate(title="Agent 上下文记忆实验", research_direction="Agent Memory")
    )

    advanced = repository.transition(project.id, ResearchStage.TOPIC_FRAMING)
    assert advanced.stage == ResearchStage.TOPIC_FRAMING

    with pytest.raises(InvalidStageTransitionError):
        repository.transition(project.id, ResearchStage.METHOD_DESIGN)
