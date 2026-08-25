"""Create Git-safe P22 result/label/delta artifacts from ignored diagnostics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.p20_failure_attribution import strict_useful


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _label(review: dict) -> str:
    if review["review_eligibility"] != "generated_answer":
        return review["review_eligibility"]
    return "strict_useful" if strict_useful(review) else "semantic_error"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--baseline-review", type=Path, required=True)
    parser.add_argument("--results-output", type=Path, required=True)
    parser.add_argument("--labels-output", type=Path, required=True)
    parser.add_argument("--deltas-output", type=Path, required=True)
    args = parser.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline_run.read_text(encoding="utf-8"))
    rows = {row["question_id"]: row for row in run["rows"]}
    baseline_rows = {row["question_id"]: row for row in baseline["rows"]}
    review = {row["question_id"]: row for row in _jsonl(args.review)}
    baseline_review = {row["question_id"]: row for row in _jsonl(args.baseline_review)}
    if not (set(rows) == set(review) == set(baseline_rows) == set(baseline_review)):
        raise ValueError("P22 and baseline inputs must cover the same questions")
    results, labels, deltas = [], [], []
    for question_id in sorted(rows):
        row, current_review = rows[question_id], review[question_id]
        results.append(
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
        labels.append(
            {
                "question_id": question_id,
                "run_sha256": current_review["run_sha256"],
                "answer_sha256": current_review["answer_sha256"],
                "review_eligibility": current_review["review_eligibility"],
                "review": current_review["review"],
            }
        )
        before = baseline_review[question_id]
        before_strict, current_strict = strict_useful(before), strict_useful(current_review)
        delta = "improved" if current_strict and not before_strict else "regressed" if before_strict and not current_strict else "same"
        deltas.append(
            {
                "question_id": question_id,
                "baseline_semantic_label": _label(before),
                "p22_semantic_label": _label(current_review),
                "baseline_outcome": baseline_rows[question_id].get("failure_stage"),
                "p22_outcome": row.get("failure_stage"),
                "route": row.get("route"),
                "delta": delta,
            }
        )
    for path, payload in (
        (args.results_output, results),
        (args.labels_output, labels),
        (args.deltas_output, deltas),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in payload), encoding="utf-8")


if __name__ == "__main__":
    main()
