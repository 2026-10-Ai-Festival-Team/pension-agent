from dataclasses import dataclass
from typing import Any, Optional, Protocol
from src.models.retrieval import SearchResult

@dataclass(frozen=True)
class GenerationResult:
    answer: str
    cited_chunk_ids: list[str]
    model: str
    latency_ms: float
    finish_reason: Optional[str] = None
    usage: Optional[dict[str, Any]] = None
    diagnostic: Optional[dict[str, Any]] = None

class AnswerGenerator(Protocol):
    def generate(self, *, question: str, contexts: list[SearchResult], query_analysis) -> GenerationResult: ...
