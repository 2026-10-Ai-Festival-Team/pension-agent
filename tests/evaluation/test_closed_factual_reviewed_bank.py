import json
from pathlib import Path

from scripts.build_closed_factual_reviewed_bank import build


ROOT = Path(__file__).resolve().parents[2]


def test_closed_factual_reviewed_bank_keeps_only_closed_source_rows() -> None:
    records, metadata = build()

    assert len(records) == 18
    assert metadata["normal_closed_count"] == 13
    assert metadata["robustness_closed_count"] == 5
    assert metadata["pending_evidence_confirmation"] == ["N-014"]
    assert all(record["question_type"] == "closed" for record in records)
    assert metadata["hcx_calls"] == 0


def test_reviewed_rubric_separates_core_from_optional_product_details() -> None:
    rows = {
        row["question_id"]: row
        for row in (json.loads(line) for line in (ROOT / "question_bank/development/closed_factual_reviewed_v1.jsonl").read_text(encoding="utf-8").splitlines() if line)
    }

    assert rows["N-009"]["required_facts"] == ["장기성장포커스는 1등급(매우 높은 위험)", "프리미엄크레딧알파 채권형은 6등급(매우 낮은 위험)"]
    assert "위험등급은 기준일 및 시장·운용실적에 따라 변경될 수 있음" in rows["N-009"]["optional_supporting_facts"]
    assert rows["N-014"]["review_status"] == "evidence_pending_additional_source_link"
    assert rows["R-006-COLLOQUIAL"]["review_notes"]["answer_style_note"].startswith("답변 첫 문장")
