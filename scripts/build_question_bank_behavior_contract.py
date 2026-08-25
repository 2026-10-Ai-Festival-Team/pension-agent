"""Derive an explicit single-turn behavior contract from question_bank_v1.

This never infers canonical planner slots or latent intents from gold answers.
Those require human annotation, so the derived spec keeps that status visible
instead of turning an unreviewed heuristic into evaluation truth.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def overall_behavior(expected: list[str]) -> str:
    actions = set(expected)
    if "answer" in actions and "clarify" in actions:
        return "answer_and_clarify"
    if "correct_user_premise" in actions:
        return "correct_and_answer"
    if "clarify" in actions:
        return "clarify"
    if actions & {"safe_response", "insufficient_information", "abstain"}:
        return "abstain"
    return "answer"


def safety_area(record: dict) -> str:
    subtype = record["subtype"].casefold()
    if "prompt" in subtype:
        return "prompt_injection"
    if record["topic"] == "recommendation":
        return "recommendation"
    if record["topic"] == "tax":
        return "tax"
    if record["topic"] == "product":
        return "product"
    if record["topic"] in {"out_of_scope", "robustness"}:
        return "out_of_scope"
    return "general"


def build_records(question_bank: Path) -> list[dict]:
    records = []
    for source in _jsonl(question_bank):
        expected = source["fixtures"]["gate_policy"]["expected_behavior"]
        records.append({
            "id": source["id"],
            "question": source["question"],
            "question_form": source["question_format"],
            "domain": [source["topic"]],
            "difficulty": source["difficulty"],
            "safety_area": safety_area(source),
            "expected_behavior": expected,
            "overall_behavior": overall_behavior(expected),
            "single_turn_required": True,
            "linguistic_variation": [],
            "intent_annotation": {
                "status": "needs_annotation",
                "intent_count": None,
                "intents": [],
            },
            "source_question_bank_id": source["id"],
        })
    return records


def main() -> None:
    source = ROOT / "evaluation/question_bank_v1.jsonl"
    output = ROOT / "evaluation/question_bank_behavior_contract_v1.jsonl"
    metadata_output = ROOT / "evaluation/question_bank_behavior_contract_v1_metadata.json"
    records = build_records(source)
    output.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    metadata_output.write_text(json.dumps({
        "version": "1.0",
        "purpose": "development behavior-contract overlay; not fresh holdout or training data",
        "source_question_bank": str(source.relative_to(ROOT)),
        "total": len(records),
        "overall_behavior_counts": dict(sorted(Counter(record["overall_behavior"] for record in records).items())),
        "safety_area_counts": dict(sorted(Counter(record["safety_area"] for record in records).items())),
        "intent_annotation_status": "all records need human decomposition annotation",
        "known_coverage_gaps": [
            "answer_and_clarify mixed-intent fixtures",
            "linguistic variation annotation: abbreviation, colloquial, typo, spacing",
            "per-intent source scope and required clarification annotations",
        ],
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(records), "overall_behavior": Counter(record["overall_behavior"] for record in records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
