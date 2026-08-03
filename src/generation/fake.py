from src.generation.base import GenerationResult
from src.models.retrieval import SearchResult


class FakeGenerator:
    """Deterministic development generator; never claims knowledge beyond evidence."""
    def generate(self, *, question: str, contexts: list[SearchResult], query_analysis) -> GenerationResult:
        if not contexts:
            return GenerationResult("제공된 문서에서 질문에 답할 근거를 찾지 못했습니다.", [], "fake", 0.0)
        return GenerationResult("검색된 근거를 확인하세요: " + contexts[0].text[:500], [contexts[0].chunk_id], "fake", 0.0)
