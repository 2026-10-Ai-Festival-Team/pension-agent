"""Apply answer-hash-bound semantic labels to the controlled P22 run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.answer_quality import REVIEW_FIELDS


P22 = {
    "accepted": {
        "R-001", "R-003", "R-004", "R-005", "R-007", "R-008", "R-009",
        "R-011", "R-013", "R-014", "R-015", "R-016", "R-017", "R-018",
        "R-020", "R-021", "R-022", "R-023", "R-025", "R-026", "R-027",
        "R-029", "R-030", "R-031", "R-032", "R-036", "R-038",
    },
    "factual_fail": {"R-011", "R-013", "R-027"},
    "coverage_fail": {"R-011", "R-013", "R-015", "R-027"},
    "grounding_fail": {"R-011", "R-013", "R-027"},
    "hallucination_fail": {"R-013", "R-027"},
    "information_limit_fail": {"R-011"},
}

NOTES = {
    "R-011": "Cited seizure-protection claims do not answer the requested tax timing.",
    "R-013": "The unconditional mandatory-transfer conclusion is not supported by the cited context.",
    "R-015": "Contribution limits/tax deduction are cited, but the requested contribution methods are not covered.",
    "R-027": "The answer lists examples but does not preserve the source table's requested classification.",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = [json.loads(line) for line in args.packet.read_text(encoding="utf-8").splitlines() if line.strip()]
    accepted = {item["question_id"] for item in packet if item["review_eligibility"] == "generated_answer"}
    if accepted != P22["accepted"]:
        raise ValueError("P22 generated answer set differs from the reviewed controlled run")
    for item in packet:
        if item["review_eligibility"] != "generated_answer":
            continue
        question_id = item["question_id"]
        review = item["review"]
        review.update(
            {
                "factual_correctness": "fail" if question_id in P22["factual_fail"] else "pass",
                "numeric_fidelity": "not_applicable",
                "requirement_coverage": "fail" if question_id in P22["coverage_fail"] else "pass",
                "evidence_grounding": "fail" if question_id in P22["grounding_fail"] else "pass",
                "hallucination": "fail" if question_id in P22["hallucination_fail"] else "pass",
                "premise_correction": "not_applicable",
                "comparison_coverage": review["comparison_coverage"],
                "information_limit_handling": "fail" if question_id in P22["information_limit_fail"] else "pass",
                "reviewer": "assistant-assisted-p22-1",
                "notes": NOTES.get(question_id, "P22 controlled-run answer·citation·retrieved context independent review"),
            }
        )
        if question_id in {"R-001", "R-005", "R-036"}:
            review["comparison_coverage"] = "pass" if review["requirement_coverage"] == "pass" else "fail"
        if set(review) < set(REVIEW_FIELDS) | {"reviewer", "notes"}:
            raise ValueError("incomplete review fields")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in packet), encoding="utf-8")


if __name__ == "__main__":
    main()
