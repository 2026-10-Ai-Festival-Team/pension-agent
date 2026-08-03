from src.models.retrieval import SearchResult


class ContextBuilder:
    def build(self, results: list[SearchResult]) -> list[SearchResult]:
        """Keep original retrieval objects so locators remain available to the API."""
        return results
