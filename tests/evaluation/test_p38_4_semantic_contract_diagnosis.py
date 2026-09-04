import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p38_4_contract_review_covers_every_missing_or_extra_action_modifier() -> None:
    result = json.loads((ROOT / "evaluation/p38_4_semantic_contract_diagnosis.json").read_text(encoding="utf-8"))

    assert result["hcx_calls"] == 0
    assert result["candidate_agent_changed"] is False
    assert result["summary"]["missing_action_modifier_atoms"] == 50
    assert result["summary"]["essential_missing_action_modifier_atoms"] > 0
    assert result["summary"]["owner_counts"]["ontology_redundancy"] > result["summary"]["owner_counts"]["prompt_salience_miss"]

    rows = {row["source_question_id"]: row for row in result["rows"]}
    early_withdrawal = rows["P38-2-002"]["action_modifier_review"]["missing_modifiers"]
    assert early_withdrawal == [{
        "atom": "before_retirement",
        "owner": "prompt_salience_miss",
        "essential": True,
        "rationale": "Early withdrawal is narrower than a generic withdrawal query.",
    }]
    historical = rows["P38-2-015"]["action_modifier_review"]["missing_modifiers"]
    assert any(item["owner"] == "gold_contract_issue" for item in historical)
