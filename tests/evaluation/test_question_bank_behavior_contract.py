import json
from pathlib import Path

from scripts.build_question_bank_behavior_contract import build_records


ROOT = Path(__file__).resolve().parents[2]


def test_behavior_contract_preserves_single_turn_behavior_without_inventing_intents() -> None:
    records = build_records(ROOT / "evaluation/question_bank_v1.jsonl")
    by_id = {record["id"]: record for record in records}

    assert len(records) == 60
    assert by_id["JSON-EVAL-024"]["overall_behavior"] == "clarify"
    assert by_id["JSON-EVAL-029"]["overall_behavior"] == "abstain"
    assert by_id["CSV-EVAL-005"]["overall_behavior"] == "correct_and_answer"
    assert all(record["single_turn_required"] for record in records)
    assert all(record["intent_annotation"]["status"] == "needs_annotation" for record in records)
    assert all(record["intent_annotation"]["intents"] == [] for record in records)


def test_committed_behavior_contract_matches_builder() -> None:
    expected = build_records(ROOT / "evaluation/question_bank_v1.jsonl")
    actual = [
        json.loads(line)
        for line in (ROOT / "evaluation/question_bank_behavior_contract_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert actual == expected
