from src.evaluation.retrieval_metrics import (
    all_evidence_at_k,
    evidence_coverage_at_k,
    first_relevant_rank,
    hit_at_k,
    reciprocal_rank,
)


def test_hit_and_reciprocal_rank():
    retrieved = ["a", "b", "c"]
    relevant = {"b"}

    assert hit_at_k(retrieved, relevant, 1) == 0.0
    assert hit_at_k(retrieved, relevant, 2) == 1.0
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert first_relevant_rank(retrieved, relevant) == 2


def test_composite_evidence_metrics():
    retrieved = ["a", "b", "c"]
    required = {"a", "c"}

    assert all_evidence_at_k(retrieved, required, 2) == 0.0
    assert all_evidence_at_k(retrieved, required, 3) == 1.0
    assert evidence_coverage_at_k(retrieved, required, 2) == 0.5
    assert evidence_coverage_at_k(retrieved, required, 3) == 1.0


def test_empty_evidence_is_not_a_hit():
    assert hit_at_k(["a"], set(), 1) == 0.0
    assert reciprocal_rank(["a"], set()) == 0.0
    assert all_evidence_at_k(["a"], set(), 1) == 0.0
    assert evidence_coverage_at_k(["a"], set(), 1) == 0.0
