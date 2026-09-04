import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p38_6a_covers_frozen_subset_without_changes_or_hcx() -> None:
    result = json.loads((ROOT / "evaluation/p38_6a_semantic_contract_attribution.json").read_text(encoding="utf-8"))

    assert result["frozen_experiment"] == {
        "hcx_calls": 0,
        "parser_modifications": 0,
        "candidate_modifications": 0,
        "gold_modifications": 0,
        "source_result_modified": False,
    }
    assert len(result["rows"]) == 18
    # Component set-difference is 45 in the frozen artifact. The earlier
    # console triage counted 43, but the attribution script checks every
    # gold-only and prediction-only component directly.
    assert sum(result["mismatch_attribution"].values()) == 45
    assert result["question_semantic_preservation"] == {"fully_preserved": 4, "meaning_lost": 11, "partially_preserved": 3}
    assert result["architecture_recommendation"]["implemented_in_this_phase"] is False


def test_p38_6a_marks_essential_and_relation_cases_without_score_correction() -> None:
    result = json.loads((ROOT / "evaluation/p38_6a_semantic_contract_attribution.json").read_text(encoding="utf-8"))
    rows = {row["question_id"]: row for row in result["rows"]}

    assert any(item["owner"] == "real_semantic_miss" and item["gold"] == "before_retirement" for item in rows["P38-2-002"]["mismatches"])
    assert any(item["owner"] == "relation_representation_mismatch" for item in rows["P38-2-014"]["mismatches"])
    assert any(item["owner"] == "contract_granularity_mismatch" for item in rows["P38-2-017"]["mismatches"])
    assert result["diagnostic_semantic_preservation"]["only_diagnostic_not_official_score"] is True
