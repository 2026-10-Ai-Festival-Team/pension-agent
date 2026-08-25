"""Create safe-to-commit P20 summaries from the ignored raw diagnostics.

The raw run and manual-review packet include answer/context text and stay in
``data/diagnostics``.  This script emits only IDs, hashes, decisions, labels,
and aggregate metrics under ``evaluation/``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


STRICT_FIELDS = ("factual_correctness", "requirement_coverage", "evidence_grounding")
COMPOUND_REFERENCE_IDS = {
    "R-002", "R-005", "R-006", "R-010", "R-024", "R-027", "R-028",
    "R-033", "R-034", "R-036", "R-037",
}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _strict(item: dict[str, Any]) -> bool | None:
    if item["review_eligibility"] != "generated_answer":
        return None
    return all(item["review"][field] == "pass" for field in STRICT_FIELDS)


def _semantic_label(item: dict[str, Any]) -> str:
    strict = _strict(item)
    if strict is True:
        return "strict_useful"
    if strict is False:
        return "semantic_error"
    return item["review_eligibility"]


def _quality_summary(review: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    generated = [item for item in review.values() if item["review_eligibility"] == "generated_answer"]
    strict = [item for item in generated if _strict(item)]
    # P16 baseline predates the route trace.  Keep the pre-registered compound
    # reference cohort so both variants use the same question subset.
    compound = [
        review[question_id]
        for question_id in COMPOUND_REFERENCE_IDS
        if review[question_id]["review_eligibility"] == "generated_answer"
    ]
    compound_strict = [item for item in compound if _strict(item)]
    return {
        "accepted_answers": len(generated),
        "semantic_correctness": sum(item["review"]["factual_correctness"] == "pass" for item in generated),
        "full_requirement_coverage": sum(item["review"]["requirement_coverage"] == "pass" for item in generated),
        "fully_grounded": sum(item["review"]["evidence_grounding"] == "pass" for item in generated),
        "strict_useful_answers": len(strict),
        "strict_e2e_useful_answer_rate": round(len(strict) / 38, 3),
        "compound_route": {
            "accepted_answers": len(compound),
            "semantic_correctness": sum(item["review"]["factual_correctness"] == "pass" for item in compound),
            "full_requirement_coverage": sum(item["review"]["requirement_coverage"] == "pass" for item in compound),
            "fully_grounded": sum(item["review"]["evidence_grounding"] == "pass" for item in compound),
            "strict_useful_answers": len(compound_strict),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p20-run", type=Path, required=True)
    parser.add_argument("--p20-review", type=Path, required=True)
    parser.add_argument("--p16-run", type=Path, required=True)
    parser.add_argument("--p16-review", type=Path, required=True)
    parser.add_argument("--results-output", type=Path, required=True)
    parser.add_argument("--labels-output", type=Path, required=True)
    parser.add_argument("--deltas-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()

    p20_payload = json.loads(args.p20_run.read_text(encoding="utf-8"))
    p16_payload = json.loads(args.p16_run.read_text(encoding="utf-8"))
    p20_rows = {row["question_id"]: row for row in p20_payload["rows"]}
    p16_rows = {row["question_id"]: row for row in p16_payload["rows"]}
    p20_review = {row["question_id"]: row for row in _jsonl(args.p20_review)}
    p16_review = {row["question_id"]: row for row in _jsonl(args.p16_review)}
    if set(p20_rows) != set(p20_review) or set(p20_rows) != set(p16_rows) or set(p20_rows) != set(p16_review):
        raise ValueError("all P16/P20 inputs must contain the same 40 question IDs")

    result_rows = []
    label_rows = []
    delta_rows = []
    for question_id in sorted(p20_rows):
        row, review = p20_rows[question_id], p20_review[question_id]
        result_rows.append(
            {
                "question_id": question_id,
                "answerable": row["answerable"],
                "route": row.get("route"),
                "evidence_sufficient": row.get("evidence_sufficient"),
                "gate_decision": row.get("evidence_reason"),
                "generator_attempted": row.get("generator_attempted", False),
                "accepted_answer": row.get("generator_called", False),
                "failure_stage": row.get("failure_stage"),
                "citation_valid": row.get("citation_valid"),
                "retrieved_chunk_ids": row.get("retrieved_chunk_ids", []),
                "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
                "elapsed_ms": row.get("elapsed_ms"),
            }
        )
        label_rows.append(
            {
                "question_id": question_id,
                "run_sha256": review["run_sha256"],
                "answer_sha256": review["answer_sha256"],
                "review_eligibility": review["review_eligibility"],
                "review": review["review"],
            }
        )
        before, before_review = p16_rows[question_id], p16_review[question_id]
        before_strict, after_strict = _strict(before_review), _strict(review)
        delta = (
            "improved" if after_strict is True and before_strict is not True
            else "regressed" if before_strict is True and after_strict is not True
            else "same"
        )
        delta_rows.append(
            {
                "question_id": question_id,
                "baseline_outcome": before.get("failure_stage"),
                "p20_outcome": row.get("failure_stage"),
                "p20_route": row.get("route"),
                "baseline_semantic_label": _semantic_label(before_review),
                "p20_semantic_label": _semantic_label(review),
                "p20_gate_decision": row.get("evidence_reason"),
                "p20_generator_attempted": row.get("generator_attempted", False),
                "p20_accepted_answer": row.get("generator_called", False),
                "delta": delta,
            }
        )

    p20_quality = _quality_summary(p20_review, p20_rows)
    p16_quality = _quality_summary(p16_review, p16_rows)
    summary = {
        "p20": {
            "preparation_parity": p20_payload["p19_preparation_parity"],
            "operational": p20_payload["summary"],
            "semantic_quality": p20_quality,
        },
        "p16_baseline_reference": {
            "operational": p16_payload["summary"],
            "semantic_quality": p16_quality,
        },
    }
    for path, payload in (
        (args.results_output, result_rows),
        (args.labels_output, label_rows),
        (args.deltas_output, delta_rows),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in payload), encoding="utf-8")
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
