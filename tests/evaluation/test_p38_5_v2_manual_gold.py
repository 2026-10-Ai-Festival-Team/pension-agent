import json
from pathlib import Path

from scripts.build_p38_5_v2_manual_gold import build


ROOT = Path(__file__).resolve().parents[2]


def test_p38_5_manual_gold_is_complete_and_non_automatic() -> None:
    rows, metadata = build()

    assert len(rows) == 48
    assert metadata["auto_converted_count"] == 0
    assert metadata["unknown_ontology_value_count"] == 0
    assert all(row["annotation_status"] == "confirmed" for row in rows)
    assert all(row["annotation_source"] == "manual" for row in rows)
    assert all(row["auto_converted"] is False for row in rows)


def test_p38_5_keeps_essential_v2_distinctions_separate() -> None:
    # Read JSONL directly: these cases cover the P38-4 real-loss categories.
    rows = {
        row["source_question_id"]: row
        for row in (json.loads(line) for line in (ROOT / "question_bank/development/semantic_contract_v2_manual_gold.jsonl").read_text(encoding="utf-8").splitlines() if line)
    }
    assert "before_retirement" in rows["P38-2-002"]["essential_qualifiers"]
    assert "combined_limit" in rows["P38-2-004"]["essential_qualifiers"]
    assert "not_tax_exempt" in rows["P38-2-005"]["essential_qualifiers"]
    assert "before_retirement" in rows["P38-2-007"]["essential_qualifiers"]
    assert {"isa_maturity", "additional_credit"} <= set(rows["P38-2-008"]["essential_qualifiers"])
    assert "in_kind" in rows["P38-2-009"]["essential_qualifiers"]
    assert "historical" in rows["P38-2-015"]["essential_qualifiers"]
    assert "tax_timing_on_transfer" in rows["P38-2-017"]["essential_qualifiers"]
    assert "partial_withdrawal_condition" in rows["P38-2-018"]["fields"]
    assert "account_closure_condition" in rows["P38-2-018"]["fields"]
