from typing import Protocol

from src.models.retrieval import SearchResult


class AnswerGenerator(Protocol):
    def generate(self, question: str, contexts: list[SearchResult]) -> str: ...
