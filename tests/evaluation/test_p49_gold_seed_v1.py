import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "evaluation/fine_tuning"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_p49_gold_seed_v1_is_human_approved_full_evidence_only():
    records = _rows(BASE / "p49_gold_seed_records_v1.jsonl")
    ledger = _rows(BASE / "p49_human_review_ledger.jsonl")
    manifest = json.loads((BASE / "p49_gold_seed_manifest_v1.json").read_text(encoding="utf-8"))

    assert len(records) == 38
    assert {record["schema_version"] for record in records} == {"p49.training_record.v2"}
    assert {record["record_type"] for record in records} == {"training_example"}
    assert {record["outcome"] for record in records} == {"supported_answer"}
    assert {record["evidence_status"] for record in records} == {"full"}
    assert all(record["review"]["status"] == "approved" for record in records)
    assert all(record["quality"]["manual_review"] == "human_approved" for record in records)
    assert len(ledger) == 38
    assert all(row["review_status"] == "approved" for row in ledger)
    assert manifest["dataset_status"] == "frozen_gold_seed_v1"
    assert manifest["human_approved"] == 38
    assert manifest["human_pending"] == 0
    assert manifest["tuning_api_calls"] == 0
