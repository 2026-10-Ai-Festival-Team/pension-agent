"""Retrieval metrics with explicit behavior for empty ground-truth evidence."""

from __future__ import annotations


def hit_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return float(bool(set(retrieved_ids[:k]) & relevant_ids))


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def all_evidence_at_k(retrieved_ids: list[str], required_ids: set[str], k: int) -> float:
    if not required_ids:
        return 0.0
    return float(required_ids.issubset(set(retrieved_ids[:k])))


def evidence_coverage_at_k(retrieved_ids: list[str], required_ids: set[str], k: int) -> float:
    if not required_ids:
        return 0.0
    return len(set(retrieved_ids[:k]) & required_ids) / len(required_ids)


def first_relevant_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> int | None:
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant_ids:
            return rank
    return None
