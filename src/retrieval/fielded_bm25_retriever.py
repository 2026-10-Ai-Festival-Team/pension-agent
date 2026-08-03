"""Rerank a stable base BM25 score with an optional table-row-key field."""

from __future__ import annotations

import numpy as np

from src.models.retrieval import SearchResponse, SearchResult


class FieldedBm25Retriever:
    def __init__(self, base_index, row_key_index) -> None:
        self.base_index, self.row_key_index = base_index, row_key_index

    def search(self, query: str, top_k: int = 10, row_key_weight: float = 0.0, query_normalizer=None) -> SearchResponse:
        if row_key_weight < 0:
            raise ValueError("row_key_weight must be non-negative")
        query_tokens = self.base_index.tokenizer.tokenize(query) if query_normalizer is None else query_normalizer.expand(query, self.base_index.tokenizer)
        scores = self.base_index.scores(query, query_normalizer=query_normalizer) + row_key_weight * self.row_key_index.scores(query_tokens)
        results = []
        for index in np.argsort(scores)[::-1]:
            if scores[index] <= 0:
                continue
            chunk = self.base_index.chunks[int(index)]
            results.append(SearchResult(rank=len(results) + 1, chunk_id=chunk.chunk_id, score=float(scores[index]), text=chunk.text, source_id=chunk.source_id, source_path=chunk.source_path, source_format=chunk.source_format, document_type=chunk.document_type, title=chunk.title, section=chunk.section, locator=chunk.locator, product_codes=chunk.product_codes, element_ids=chunk.element_ids, metadata={"retriever": "fielded_bm25", "row_key_weight": row_key_weight}))
            if len(results) == top_k:
                break
        return SearchResponse(query=query, tokenizer=self.base_index.tokenizer.name, total_candidates=len(self.base_index.chunks), results=results)
