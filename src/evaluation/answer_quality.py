"""Build and summarize a manual semantic-quality review packet.

This module deliberately does not use an LLM to score answers.  Retrieval and
citation-contract facts are measured automatically; factual correctness and
claim grounding are reviewer labels tied to the exact generated answer.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REVIEW_FIELDS = (
    "factual_correctness",
    "numeric_fidelity",
    "requirement_coverage",
    "evidence_grounding",
    "hallucination",
    "premise_correction",
    "comparison_coverage",
    "information_limit_handling",
)
REVIEW_VALUES = {"pass", "fail", "not_applicable", "not_reviewed"}


def answer_sha256(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def review_eligibility(row: dict[str, Any]) -> str:
    if row.get("status_code") != 200:
        return "api_failure"
    if not row.get("answerable"):
        return "unsupported_or_personal_policy"
    if row.get("generator_called"):
        return "generated_answer"
    if row.get("generator_attempted"):
        return "generation_or_citation_rejection"
    return "evidence_policy_rejection"


def build_review_packet(
    run_rows: list[dict[str, Any]], questions: list[Any], run_sha256: str
) -> list[dict[str, Any]]:
    questions_by_id = {question.question_id: question for question in questions}
    if len(questions_by_id) != len(questions):
        raise ValueError("question_id must be unique")
    seen_ids: set[str] = set()
    packet: list[dict[str, Any]] = []
    for row in run_rows:
        question_id = row["question_id"]
        if question_id in seen_ids or question_id not in questions_by_id:
            raise ValueError(f"invalid run question_id: {question_id}")
        seen_ids.add(question_id)
        question = questions_by_id[question_id]
        answer = row.get("answer", "")
        eligibility = review_eligibility(row)
        review = {field: "not_reviewed" for field in REVIEW_FIELDS}
        if question.evidence_requirement != "all":
            review["comparison_coverage"] = "not_applicable"
        if not question.answerable:
            review["numeric_fidelity"] = "not_applicable"
            review["comparison_coverage"] = "not_applicable"
        packet.append(
            {
                "question_id": question_id,
                "run_sha256": run_sha256,
                "answer_sha256": answer_sha256(answer),
                "review_eligibility": eligibility,
                "question": question.question,
                "category": question.category,
                "answerable": question.answerable,
                "evidence_requirement": question.evidence_requirement,
                "required_terms": question.required_terms,
                "gold_direct_chunk_ids": sorted(question.direct_evidence_ids),
                "gold_relevant_chunk_ids": sorted(question.all_relevant_ids),
                "retrieved_chunk_ids": row.get("retrieved_chunk_ids", []),
                "cited_chunk_ids": row.get("cited_chunk_ids", []),
                "retrieved_context": row.get("retrieved_context", ""),
                "answer": answer,
                "system": {
                    "status_code": row.get("status_code"),
                    "failure_stage": row.get("failure_stage"),
                    "generator_attempted": row.get("generator_attempted", False),
                    "generator_called": row.get("generator_called", False),
                    "citation_valid": row.get("citation_valid"),
                    "generation_error": row.get("generation_error"),
                    "direct_evidence_hit_at_10": row.get("direct_evidence_hit_at_10"),
                    "all_relevant_evidence_hit_at_10": row.get("all_relevant_evidence_hit_at_10"),
                },
                "review": {**review, "reviewer": "", "notes": ""},
            }
        )
    if seen_ids != set(questions_by_id):
        raise ValueError("run rows and evaluation questions do not match")
    return packet


def load_completed_reviews(path: Path, expected_run_sha256: str) -> list[dict[str, Any]]:
    reviews = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for review in reviews:
        if review.get("run_sha256") != expected_run_sha256:
            raise ValueError("review packet was created from a different run")
        for field in REVIEW_FIELDS:
            if review.get("review", {}).get(field) not in REVIEW_VALUES:
                raise ValueError(f"invalid {field} value")
    return reviews


def summarize_review_packet(packet: list[dict[str, Any]]) -> dict[str, Any]:
    automated = {
        "question_count": len(packet),
        "answerable_count": sum(item["answerable"] for item in packet),
        "generated_answer_count": sum(item["review_eligibility"] == "generated_answer" for item in packet),
        "unsupported_or_personal_policy_count": sum(item["review_eligibility"] == "unsupported_or_personal_policy" for item in packet),
        "direct_evidence_hit_at_10": sum(bool(item["system"]["direct_evidence_hit_at_10"]) for item in packet if item["answerable"]),
        "all_evidence_hit_at_10": sum(bool(item["system"]["all_relevant_evidence_hit_at_10"]) for item in packet if item["evidence_requirement"] == "all"),
        "comparison_question_count": sum(item["evidence_requirement"] == "all" for item in packet),
    }
    reviewed = [item for item in packet if item["review"]["factual_correctness"] != "not_reviewed"]
    manual: dict[str, Any] = {"reviewed_answer_count": len(reviewed)}
    for field in REVIEW_FIELDS:
        manual[field] = dict(Counter(item["review"][field] for item in reviewed))
    return {"automated": automated, "manual": manual}
