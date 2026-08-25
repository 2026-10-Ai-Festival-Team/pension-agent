"""Separate P20 provider incidents from answer-quality outcomes."""
from __future__ import annotations

from collections import Counter
from typing import Any


STRICT_FIELDS = ("factual_correctness", "requirement_coverage", "evidence_grounding")


def _history(row: dict[str, Any]) -> list[dict[str, Any]]:
    return row.get("generation_attempt_history", [])


def has_429(row: dict[str, Any]) -> bool:
    return any(item.get("http_status") == 429 for item in _history(row))


def provider_retry_exhausted(row: dict[str, Any]) -> bool:
    return bool(
        row.get("answerable")
        and row.get("generator_attempted")
        and not row.get("generator_called")
        and row.get("generation_error") == "GenerationError"
        and has_429(row)
    )


def strict_useful(review: dict[str, Any]) -> bool:
    return bool(
        review.get("review_eligibility") == "generated_answer"
        and all(review["review"].get(field) == "pass" for field in STRICT_FIELDS)
    )


def failure_owner(row: dict[str, Any], review: dict[str, Any]) -> str:
    if not row.get("answerable"):
        return "unsupported_policy"
    if not row.get("generator_attempted"):
        return "pre_generation_gate"
    if provider_retry_exhausted(row):
        return "provider_retry_exhaustion"
    if not row.get("generation_model"):
        return "hcx_schema_or_transport"
    if not row.get("generator_called"):
        return "citation_validation"
    if not strict_useful(review):
        return "post_hcx_semantic_quality"
    return "strict_useful"


def summarize(rows: list[dict[str, Any]], reviews: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if {row["question_id"] for row in rows} != set(reviews):
        raise ValueError("rows and reviews must have the same question IDs")
    answerable = [row for row in rows if row["answerable"]]
    strict = [row for row in answerable if strict_useful(reviews[row["question_id"]])]
    provider_exhausted = [row for row in answerable if provider_retry_exhausted(row)]
    provider_affected = [row for row in answerable if has_429(row)]
    provider_clean = [row for row in answerable if not has_429(row)]
    provider_evaluable = [row for row in answerable if not provider_retry_exhausted(row)]
    accepted = [row for row in answerable if row.get("generator_called")]
    semantic_failures = [row for row in accepted if not strict_useful(reviews[row["question_id"]])]
    histories = [item for row in rows for item in _history(row)]
    required_timing_keys = {
        "attempt_started_offset_ms",
        "request_started_offset_ms",
        "request_completed_offset_ms",
        "rate_limit_wait_ms",
    }
    owners = {
        row["question_id"]: failure_owner(row, reviews[row["question_id"]])
        for row in rows
    }
    return {
        "unconditional_strict_e2e": {"useful": len(strict), "denominator": len(answerable), "rate": round(len(strict) / len(answerable), 3)},
        "provider_successfully_evaluable": {
            "definition": "answerable questions excluding only provider 429 retry exhaustion; recovered 429 responses remain evaluable",
            "useful": sum(strict_useful(reviews[row["question_id"]]) for row in provider_evaluable),
            "denominator": len(provider_evaluable),
            "rate": round(sum(strict_useful(reviews[row["question_id"]]) for row in provider_evaluable) / len(provider_evaluable), 3),
        },
        "strict_no_429_subset": {
            "definition": "answerable questions with no 429 in any provider attempt",
            "useful": sum(strict_useful(reviews[row["question_id"]]) for row in provider_clean),
            "denominator": len(provider_clean),
            "rate": round(sum(strict_useful(reviews[row["question_id"]]) for row in provider_clean) / len(provider_clean), 3),
        },
        "normal_hcx_semantic": {
            "definition": "accepted answers: provider response, structured parsing, and citation validation all passed",
            "accepted": len(accepted),
            "strict_useful": len(accepted) - len(semantic_failures),
            "semantic_failure": len(semantic_failures),
            "semantic_failure_question_ids": [row["question_id"] for row in semantic_failures],
        },
        "provider_incident": {
            "provider_affected_questions": len(provider_affected),
            "provider_affected_question_ids": [row["question_id"] for row in provider_affected],
            "provider_retry_exhaustion": len(provider_exhausted),
            "provider_retry_exhaustion_question_ids": [row["question_id"] for row in provider_exhausted],
            "provider_recovered_after_429": sum(row.get("generator_called", False) for row in provider_affected),
            "http_429_attempts": sum(item.get("http_status") == 429 for item in histories),
            "retry_after_seen": sum(item.get("retry_after_seconds") is not None for item in histories),
            "historical_attempt_timing_complete": sum(required_timing_keys.issubset(item) for item in histories),
            "historical_attempt_count": len(histories),
        },
        "owner_counts": dict(Counter(owners.values())),
        "owner_by_question_id": owners,
    }
