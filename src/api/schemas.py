from typing import Any, Optional
from pydantic import BaseModel, Field
from src.models.chunk import ChunkLocator


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)


class Evidence(BaseModel):
    chunk_id: str; source_id: str; source_path: str; locator: ChunkLocator; element_ids: list[str]; score: float; text: str


class AnswerResponse(BaseModel):
    question_id: Optional[str] = None
    question: str
    retrieved_context: list[Evidence]
    think_trace: dict[str, Any]
    answer: str


class EvaluationAnswerResponse(BaseModel):
    question_id: Optional[str] = None
    question: str
    retrieved_context: str
    think_trace: dict[str, Any]
    answer: str
