from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnswerMode(str, Enum):
    ANSWER = "ANSWER"
    CLARIFY = "CLARIFY"
    ABSTAIN = "ABSTAIN"


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    page: int | None = None
    topic: str = "other"
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(DocumentChunk):
    score: float


class QuestionAnalysis(BaseModel):
    intent: str = "other"
    entities: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    needs_calculation: bool = False
    needs_clarification: bool = False
    missing_information: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    question_id: str
    question: str
    retrieved_context: str
    think_trace: str
    answer: str


class HealthResponse(BaseModel):
    status: str = "ok"
