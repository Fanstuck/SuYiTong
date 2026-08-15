"""科研项目与阶段状态机。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ResearchMode(StrEnum):
    FULL = "full"
    SEMI = "semi"


class ResearchStage(StrEnum):
    INTAKE = "intake"
    TOPIC_FRAMING = "topic_framing"
    LITERATURE_REVIEW = "literature_review"
    METHOD_DESIGN = "method_design"
    EXPERIMENT = "experiment"
    WRITING = "writing"
    QUALITY_REVIEW = "quality_review"
    DELIVERED = "delivered"


STAGE_SEQUENCE: tuple[ResearchStage, ...] = tuple(ResearchStage)


class ProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    research_direction: str = Field(min_length=2, max_length=100)
    mode: ResearchMode = ResearchMode.SEMI


class StageTransition(BaseModel):
    target_stage: ResearchStage


class ResearchProject(BaseModel):
    id: str
    title: str
    research_direction: str
    mode: ResearchMode
    stage: ResearchStage
    created_at: datetime
    updated_at: datetime


def can_transition(current: ResearchStage, target: ResearchStage) -> bool:
    """首期只允许留在当前阶段或向下一个阶段推进，禁止跳过质量门。"""

    if current == target:
        return True
    current_index = STAGE_SEQUENCE.index(current)
    return current_index + 1 < len(STAGE_SEQUENCE) and STAGE_SEQUENCE[current_index + 1] == target

