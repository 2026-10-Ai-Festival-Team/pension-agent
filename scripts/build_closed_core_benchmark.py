"""Build the development-only Closed Core benchmark from question_bank_v1.

The benchmark intentionally excludes personalised recommendation, clarify,
abstain, and other advisory/safety behaviour.  It is a source-grounded factual
QA regression set, not a fresh generalisation holdout.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def closed_core_group(record: dict) -> str | None:
    """Classify factual, document-answerable records without source-ID rules."""
    expected = record["fixtures"]["gate_policy"]["expected_behavior"][0]
    if expected not in {"answer", "correct_user_premise"}:
        return None
    topic = record["topic"]
    if topic == "recommendation":
        return None
    if topic in {"institution", "pension_system"}:
        return "institution_closed"
    if topic == "tax":
        return "tax_closed"
    if topic == "procedure":
        return "procedure_closed"
    if topic == "compound":
        return "compound_closed"
    if topic == "product":
        return "product_fact_comparison" if "comparison" in record["subtype"] else "product_fact"
    return None


def build_records(question_bank: Path) -> list[dict]:
    records = []
    for source in _jsonl(question_bank):
        group = closed_core_group(source)
        if group is None:
            continue
        records.append({
            "id": source["id"],
            "question": source["question"],
            "closed_core_group": group,
            "expected_behavior": source["expected_behavior"],
            "requirements": source["requirements"],
            "required_evidence": source["required_evidence"],
            "forbidden_claims": source["forbidden_claims"],
            "fixtures": {
                "retrieval": source["fixtures"]["retrieval"],
                "grounding": source["fixtures"]["grounding"],
                "generation": source["fixtures"]["generation"],
                "gate_policy": source["fixtures"]["gate_policy"],
            },
            "source_set": source["source_set"],
            "source_item_id": source["source_item_id"],
        })
    return records


def main() -> None:
    question_bank = ROOT / "evaluation/question_bank_v1.jsonl"
    output = ROOT / "evaluation/closed_core_benchmark_v1.jsonl"
    metadata = ROOT / "evaluation/closed_core_benchmark_v1_metadata.json"
    records = build_records(question_bank)
    output.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    metadata.write_text(json.dumps({
        "version": "1.0",
        "purpose": "development-only closed factual QA regression; not a fresh holdout",
        "source_question_bank": "evaluation/question_bank_v1.jsonl",
        "total": len(records),
        "group_counts": dict(sorted(Counter(record["closed_core_group"] for record in records).items())),
        "excluded": [
            "personalized recommendation and suitability",
            "clarify/abstain/safe-response policy cases",
            "out-of-scope and prompt-injection cases",
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(records), "groups": Counter(record["closed_core_group"] for record in records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
