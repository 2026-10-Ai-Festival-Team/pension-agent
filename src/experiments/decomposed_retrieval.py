"""P6-B: requirement별 검색 결과를 합치는 실험 전용 도구."""
from __future__ import annotations

from dataclasses import dataclass

from src.models.retrieval import SearchResult


@dataclass(frozen=True)
class DecomposedRetrievalResult:
    slot_results: dict[str, tuple[SearchResult, ...]]
    merged_results: tuple[SearchResult, ...]


def retrieve_by_requirement(retriever, slot_queries: dict[str, str], top_k: int = 5) -> DecomposedRetrievalResult:
    """동일 Retriever에 requirement별 query만 달리해 호출하고 중복을 제거한다."""
    slot_results: dict[str, tuple[SearchResult, ...]] = {}
    merged: list[SearchResult] = []
    seen: set[str] = set()
    for slot_name, query in slot_queries.items():
        results = tuple(retriever.search(query, top_k=top_k).results)
        slot_results[slot_name] = results
        for result in results:
            if result.chunk_id not in seen:
                merged.append(result)
                seen.add(result.chunk_id)
    # A merged candidate list has a deterministic order but no comparable global BM25 rank.
    ranked = tuple(item.model_copy(update={"rank": rank}) for rank, item in enumerate(merged, start=1))
    return DecomposedRetrievalResult(slot_results, ranked)
