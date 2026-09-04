"""Pure helpers for classifying a source-to-answer coverage audit."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


VALID_OWNERS = frozenset(
    {
        "true_data_gap",
        "parsing_or_ocr_gap",
        "retrieval_recall",
        "evidence_matcher",
        "selection",
    }
)


def coverage_owner(
    *,
    raw_evidence_exists: bool,
    corpus_evidence_exists: bool,
    semantic_evidence_in_candidates: bool,
    selected_evidence_supports_requirement: bool,
) -> str:
    """Return the first pipeline layer that prevents an evidence-backed answer.

    The ordering deliberately follows the data path.  A semantic-equivalent
    candidate counts as retrieval success even when a manually labelled
    *exact* gold chunk was not returned.
    """

    if not raw_evidence_exists:
        return "true_data_gap"
    if not corpus_evidence_exists:
        return "parsing_or_ocr_gap"
    if not semantic_evidence_in_candidates:
        return "retrieval_recall"
    if not selected_evidence_supports_requirement:
        return "evidence_matcher"
    return "selection"


def owner_counts(records: Iterable[dict[str, str]]) -> dict[str, int]:
    """Return deterministic counts containing every supported audit owner."""

    counts = Counter(record["primary_owner"] for record in records)
    unknown = set(counts) - VALID_OWNERS
    if unknown:
        raise ValueError(f"Unsupported coverage owner: {sorted(unknown)}")
    return {owner: counts[owner] for owner in sorted(VALID_OWNERS)}
