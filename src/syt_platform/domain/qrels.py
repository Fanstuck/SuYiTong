"""盲化人工相关性标注集（qrels）领域模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class QrelJudgment(BaseModel):
    relevance: int = Field(ge=0, le=3)
    rationale: str = Field(default="", max_length=1000)
    assessor_id: str = Field(min_length=2, max_length=100)
    judged_at: datetime


class QrelsPoolItem(BaseModel):
    query: str
    paper_id: str
    title: str
    abstract: str
    year: int | None = None
    doi: str = ""
    judgment: QrelJudgment | None = None


class QrelsCreateRequest(BaseModel):
    assessor_id: str = Field(min_length=2, max_length=100)
    pool_depth: int = Field(default=10, ge=5, le=30)
    instructions: str = Field(default="", max_length=3000)


class QrelsJudgmentInput(BaseModel):
    query: str
    paper_id: str
    relevance: int = Field(ge=0, le=3)
    rationale: str = Field(default="", max_length=1000)


class QrelsJudgmentBatch(BaseModel):
    assessor_id: str = Field(min_length=2, max_length=100)
    judgments: list[QrelsJudgmentInput] = Field(min_length=1, max_length=500)


class QrelsSet(BaseModel):
    id: str
    project_id: str
    literature_run_id: str
    retrieval_run_id: str
    status: str
    pool_depth: int
    assessor_id: str
    instructions: str
    items: list[QrelsPoolItem]
    query_count: int
    judgment_count: int
    frozen_sha256: str | None = None
    created_at: datetime
    updated_at: datetime
    frozen_at: datetime | None = None

