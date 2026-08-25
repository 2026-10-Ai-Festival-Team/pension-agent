"""P23-B: classify P22 compound outcomes without another HCX call."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.retrieval_dataset import load_questions


COMPOUND_IDS = (
    "R-002", "R-005", "R-006", "R-010", "R-024", "R-027", "R-028",
    "R-033", "R-034", "R-036", "R-037",
)

CLASSIFICATION = {
    "R-002": ("citation_contract", "required evidence was selected; HCX returned an invalid citation identifier"),
    "R-005": ("success", "all required evidence is present and the accepted answer is strict useful"),
    "R-006": ("citation_contract", "required evidence was selected; HCX returned an invalid citation identifier"),
    "R-010": ("evidence_incomplete", "pre-generation gate blocked because a required tax/exception slot was not covered"),
    "R-024": ("retrieval_missing", "product-field requirement remained incomplete before generation"),
    "R-027": ("generation_misread", "the classification table was selected, but the answer reduced it to examples rather than the requested classification"),
    "R-028": ("retrieval_missing", "product-field requirement remained incomplete before generation"),
    "R-033": ("provider_retry_exhaustion", "provider 429 exhaustion prevented evaluation of selected product evidence"),
    "R-034": ("provider_retry_exhaustion", "provider 429 exhaustion prevented evaluation of selected product evidence"),
    "R-036": ("success", "both requested product fields are answered with selected evidence"),
    "R-037": ("retrieval_missing", "DB/DC operation requirements remained incomplete before generation"),
}


def _reviews(path: Path) -> dict[str, dict]:
    return {item["question_id"]: item for item in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=ROOT / "data/diagnostics/p22_full_hcx.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/diagnostics/p22_full_reviewed.jsonl")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p23_compound_failure_analysis.json")
    args = parser.parse_args()
    run = json.loads(args.run.read_text(encoding="utf-8"))
    rows = {row["question_id"]: row for row in run["rows"]}
    reviews = _reviews(args.reviews)
    questions = {question.question_id: question for question in load_questions(args.questions)}
    records = []
    for question_id in COMPOUND_IDS:
        row, review = rows[question_id], reviews[question_id]
        failure_type, rationale = CLASSIFICATION[question_id]
        slots = (row.get("requirement_plan") or {}).get("slots", [])
        records.append(
            {
                "question_id": question_id,
                "question": questions[question_id].question,
                "route": row.get("route"),
                "requirement_slots": [slot["name"] for slot in slots],
                "candidate_chunk_ids": row.get("candidate_chunk_ids", []),
                "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
                "evidence_sufficient": row.get("evidence_sufficient"),
                "gate_decision": row.get("evidence_reason"),
                "generator_attempted": row.get("generator_attempted"),
                "accepted_answer": row.get("generator_called"),
                "semantic_review_eligibility": review["review_eligibility"],
                "semantic_label": (
                    "strict_useful"
                    if review["review_eligibility"] == "generated_answer"
                    and all(review["review"][field] == "pass" for field in ("factual_correctness", "requirement_coverage", "evidence_grounding"))
                    else "semantic_error" if review["review_eligibility"] == "generated_answer" else review["review_eligibility"]
                ),
                "failure_type": failure_type,
                "rationale": rationale,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"source_run": "P22", "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "failure_types": {key: sum(record["failure_type"] == key for record in records) for key in sorted({record["failure_type"] for record in records})}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
