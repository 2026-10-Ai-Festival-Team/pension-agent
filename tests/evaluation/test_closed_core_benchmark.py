import json
from pathlib import Path

from scripts.build_closed_core_benchmark import build_records


ROOT = Path(__file__).resolve().parents[2]


def test_closed_core_benchmark_excludes_advisory_and_safety_cases() -> None:
    records = build_records(ROOT / "evaluation/question_bank_v1.jsonl")

    assert records
    assert {record["closed_core_group"] for record in records} == {
        "institution_closed",
        "tax_closed",
        "procedure_closed",
        "compound_closed",
        "product_fact",
        "product_fact_comparison",
    }
    assert all(record["closed_core_group"] for record in records)
    assert all("recommendation" not in record["closed_core_group"] for record in records)
    assert all(record["expected_behavior"] in (["answer"], ["correct_user_premise"]) for record in records)


def test_committed_closed_core_benchmark_matches_builder() -> None:
    expected = build_records(ROOT / "evaluation/question_bank_v1.jsonl")
    actual = [
        json.loads(line)
        for line in (ROOT / "evaluation/closed_core_benchmark_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert actual == expected
