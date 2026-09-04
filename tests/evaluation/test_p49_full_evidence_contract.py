import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "evaluation/fine_tuning"


def _rows(name: str) -> list[dict]:
    path = BASE / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_p49_full_evidence_drafts_have_explicit_supported_answer_contract():
    records = _rows("p49_draft_gold_training_records_v4.jsonl") + _rows(
        "p49_draft_contrastive_records_v4.jsonl"
    )

    assert len(records) == 38
    assert {record["schema_version"] for record in records} == {"p49.training_draft.v2"}
    assert {record["outcome"] for record in records} == {"supported_answer"}
    assert {record["evidence_status"] for record in records} == {"full"}
    assert all(record["missing_conditions"] == [] for record in records)
    assert all(record["unsupported_requirements"] == [] for record in records)
    assert all(record["completion"].endswith("[유의사항] 없음") for record in records)


def test_p49_full_evidence_contract_qa_is_not_a_human_approval():
    qa = json.loads((BASE / "p49_dataset_qa_results_v4.json").read_text(encoding="utf-8"))
    manifest = json.loads((BASE / "p49_dataset_manifest_v4.json").read_text(encoding="utf-8"))

    assert qa["automatic_qa_pass"] == 38
    assert qa["human_approved"] == 0
    assert qa["human_pending"] == 38
    assert manifest["dataset_status"] == "draft_awaiting_human_approval"
    assert manifest["answer_policy_contract"]["outcome"] == "supported_answer"
