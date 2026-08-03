from src.models.retrieval import SearchResult


class ContextBuilder:
    def build(self, results: list[SearchResult], max_contexts: int = 5) -> list[SearchResult]:
        """Keep original retrieval objects so locators remain available to the API."""
        seen, selected = set(), []
        for result in results:
            if result.chunk_id not in seen:
                selected.append(result); seen.add(result.chunk_id)
            if len(selected) == max_contexts:
                break
        return selected
