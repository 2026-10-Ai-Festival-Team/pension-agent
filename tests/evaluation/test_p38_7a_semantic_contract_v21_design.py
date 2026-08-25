import json
from pathlib import Path

from scripts.design_p38_7a_contract_v21 import main


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "evaluation/p38_7a_semantic_contract_v21_design.json"


def test_p38_7a_design_accounts_for_frozen_attribution_without_runtime_changes() -> None:
    main()
    result = json.loads(OUTPUT.read_text(encoding="utf-8"))

    assert result["status"] == "design_only"
    assert result["frozen_boundary"]["hcx_calls"] == 0
    assert result["frozen_boundary"]["v2_parser_prompt_ontology_composer_modified"] is False
    assert len(result["question_design_mapping"]) == 18
    assert result["frozen_mismatch_accounting"] == {
        "contract_equivalent": 2,
        "contract_granularity_mismatch": 1,
        "real_semantic_miss": 17,
        "relation_representation_mismatch": 9,
        "unsupported_extra": 16,
    }


def test_p38_7a_keeps_directional_transfer_and_moves_generic_comparison_to_deterministic_layer() -> None:
    main()
    result = json.loads(OUTPUT.read_text(encoding="utf-8"))
    output = result["v21_contract"]["hcx_output"]

    assert "directional_transfer_relations" in output
    assert "generic_comparison_relation" in result["v21_contract"]["not_hcx_output"]
    assert any("comparison intent" in item for item in result["v21_contract"]["deterministic_derivations"])
