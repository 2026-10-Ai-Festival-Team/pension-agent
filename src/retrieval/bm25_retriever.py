from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from src.retrieval.retriever import Retriever
from src.schemas.models import DocumentChunk, RetrievalResult


TOKEN_PATTERN = re.compile(r"[가-힣]+|[A-Za-z]+|\d+(?:[.,]\d+)*%?")


def tokenize_korean(text: str) -> list[str]:
    """Dependency-free baseline: eojeol-like terms plus Korean character bigrams."""
    tokens: list[str] = []
    for term in TOKEN_PATTERN.findall(text.lower()):
        normalized = term.replace(",", "")
        tokens.append(normalized)
        if re.fullmatch(r"[가-힣]{3,}", normalized):
            tokens.extend(normalized[i : i + 2] for i in range(len(normalized) - 1))
    return tokens


class BM25Retriever(Retriever):
    def __init__(self, chunks: list[DocumentChunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize_korean(chunk.text) for chunk in chunks]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokens]
        self.avgdl = sum(map(len, self.tokens)) / len(self.tokens) if self.tokens else 0.0
        self.document_frequency = Counter()
        for tokens in self.tokens:
            self.document_frequency.update(set(tokens))

    @classmethod
    def from_jsonl(cls, path: Path) -> "BM25Retriever":
        if not path.exists():
            return cls([])
        chunks = [DocumentChunk.model_validate_json(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
        return cls(chunks)

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        if not query.strip() or top_k <= 0 or not self.chunks:
            return []
        query_terms = tokenize_korean(query)
        n_docs = len(self.chunks)
        scores: list[tuple[float, int]] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            document_length = len(self.tokens[index])
            for term in query_terms:
                tf = frequencies[term]
                if not tf:
                    continue
                df = self.document_frequency[term]
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                denominator = tf + self.k1 * (1 - self.b + self.b * document_length / (self.avgdl or 1))
                score += idf * tf * (self.k1 + 1) / denominator
            if score > 0:
                scores.append((score, index))
        scores.sort(key=lambda item: (-item[0], item[1]))
        return [
            RetrievalResult(**self.chunks[index].model_dump(), score=round(score, 6))
            for score, index in scores[:top_k]
        ]


def save_chunks(chunks: list[DocumentChunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(chunk.model_dump_json() for chunk in chunks)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
