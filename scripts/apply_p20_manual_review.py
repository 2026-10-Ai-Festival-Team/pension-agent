"""Apply the independent, answer-hash-bound P20 semantic review labels.

This is deliberately a record of the P20 answers, not a projection of P16
labels.  It refuses to write if the final P20 run has a different accepted
answer set, which prevents a later provider rerun from silently inheriting
these labels.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.answer_quality import REVIEW_FIELDS


P20 = {
    "accepted": {
        "R-007", "R-008", "R-009", "R-011", "R-020", "R-021", "R-022",
        "R-023", "R-025", "R-026", "R-027", "R-029", "R-030", "R-031",
        "R-032", "R-033", "R-034", "R-036",
    },
    # R-011 answers a different, cited topic. R-034 mistakes a cost example
    # for the requested total-fee value.
    "factual_fail": {"R-011", "R-034"},
    "numeric_fail": {"R-034"},
    # R-033 gives the product name but omits the requested risk grade.
    "coverage_fail": {"R-011", "R-033", "R-034"},
    "grounding_fail": {"R-011", "R-034"},
    "hallucination_fail": {"R-034"},
    "information_limit_fail": {"R-011"},
}

NOTES = {
    "R-011": "Cited claims concern seizure protection, not the requested tax timing.",
    "R-033": "The product name is supported, but the requested risk grade is omitted.",
    "R-034": "A time-based cost example is presented as the requested total-fee value.",
}


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    packet = _load(args.packet)
    accepted = {item["question_id"] for item in packet if item["review_eligibility"] == "generated_answer"}
    if accepted != P20["accepted"]:
        raise ValueError("P20 generated answer set differs from the reviewed final run")

    for item in packet:
        if item["review_eligibility"] != "generated_answer":
            continue
        question_id = item["question_id"]
        review = item["review"]
        review.update(
            {
                "factual_correctness": "fail" if question_id in P20["factual_fail"] else "pass",
                "numeric_fidelity": (
                    "fail" if question_id in P20["numeric_fail"] else "not_applicable"
                ),
                "requirement_coverage": "fail" if question_id in P20["coverage_fail"] else "pass",
                "evidence_grounding": "fail" if question_id in P20["grounding_fail"] else "pass",
                "hallucination": "fail" if question_id in P20["hallucination_fail"] else "pass",
                "premise_correction": "not_applicable",
                "comparison_coverage": review["comparison_coverage"],
                "information_limit_handling": (
                    "fail" if question_id in P20["information_limit_fail"] else "pass"
                ),
                "reviewer": "assistant-assisted-p20-1",
                "notes": NOTES.get(question_id, "P20 current answer·citation·retrieved context independent review"),
            }
        )
        if question_id == "R-036":
            review["comparison_coverage"] = "pass"
        if set(review) < set(REVIEW_FIELDS) | {"reviewer", "notes"}:
            raise ValueError("incomplete review fields")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in packet),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
