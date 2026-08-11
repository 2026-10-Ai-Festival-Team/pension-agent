"""Requirement별 보조 검색 후보를 실험적으로 합친다.

전역 BM25 설정이나 원 질문의 Top-k를 변경하지 않는다. 명시적인 requirement
query가 있는 경우에만 같은 고정 retriever에 추가 질의를 보내며, 기존 후보를
항상 보존한다.
"""
from __future__ import annotations

from collections.abc import Iterable

from src.experiments.multi_evidence import RequirementCase
from src.models.retrieval import SearchResult


def expand_requirement_candidates(
    case: RequirementCase | None,
    base_results: Iterable[SearchResult],
    retriever: object,
    *,
    top_k: int,
) -> tuple[SearchResult, ...]:
    """고정 Top-k에 requirement-specific 후보를 중복 없이 추가한다."""
    candidates = list(base_results)
    seen = {result.chunk_id for result in candidates}
    if case is None or top_k <= 0:
        return tuple(candidates)

    queries = []
    for slot in case.slots:
        if slot.retrieval_query and slot.retrieval_query not in queries:
            queries.append(slot.retrieval_query)
    for query in queries:
        for result in retriever.search(query, top_k=top_k).results:
            if result.chunk_id not in seen:
                candidates.append(result)
                seen.add(result.chunk_id)
    return tuple(candidates)
