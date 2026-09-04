import json
from pathlib import Path

from scripts.build_question_bank import build_records


ROOT = Path(__file__).resolve().parents[2]


def test_question_bank_preserves_colliding_source_ids_in_separate_namespaces() -> None:
    records = build_records(ROOT / "eval_questions_final.csv", ROOT / "eval_questions.json")

    assert len(records) == 60
    assert {"CSV-EVAL-001", "JSON-EVAL-001"} <= {record["id"] for record in records}
    assert len({record["id"] for record in records}) == 60


def test_json_question_bank_records_preserve_evidence_and_safety_contracts() -> None:
    records = build_records(ROOT / "eval_questions_final.csv", ROOT / "eval_questions.json")
    record = next(item for item in records if item["id"] == "JSON-EVAL-030")

    assert record["expected_behavior"] == ["abstain"]
    assert record["forbidden_claims"]
    assert record["fixtures"]["gate_policy"]["expected_behavior"] == ["abstain"]
    assert record["planner_slot_status"] == "needs_annotation"


def test_committed_question_bank_matches_source_transform() -> None:
    expected = build_records(ROOT / "eval_questions_final.csv", ROOT / "eval_questions.json")
    actual = [json.loads(line) for line in (ROOT / "evaluation/question_bank_v1.jsonl").read_text(encoding="utf-8").splitlines()]

    assert actual == expected
