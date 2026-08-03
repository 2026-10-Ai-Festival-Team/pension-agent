from src.models.retrieval import SearchResult


class FakeGenerator:
    """Deterministic development generator; never claims knowledge beyond evidence."""
    def generate(self, question: str, contexts: list[SearchResult]) -> str:
        if not contexts:
            return "제공된 문서에서 질문에 답할 근거를 찾지 못했습니다."
        return "검색된 근거를 확인하세요: " + contexts[0].text[:500]
