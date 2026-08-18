from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.models import RetrievalResult


class Retriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        raise NotImplementedError
