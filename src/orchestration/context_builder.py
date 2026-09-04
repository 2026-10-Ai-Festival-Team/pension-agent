from src.models.retrieval import SearchResult
from src.models.document import AuthorityLevel, SourceType


class ContextBuilder:
    def build(self, results: list[SearchResult], max_contexts: int = 5) -> list[SearchResult]:
        """원본·1차 근거를 우선하되 locator가 있는 검색 객체를 그대로 보존한다."""
        seen, selected = set(), []
        ordered = sorted(
            results,
            key=lambda result: (
                result.source_type != SourceType.ORIGINAL
                or result.authority_level != AuthorityLevel.PRIMARY,
                result.rank,
            ),
        )
        for result in ordered:
            if result.chunk_id not in seen:
                selected.append(result); seen.add(result.chunk_id)
            if len(selected) == max_contexts:
                break
        return selected
