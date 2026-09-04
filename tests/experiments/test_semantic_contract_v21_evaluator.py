import json
from pathlib import Path

from src.experiments.semantic_contract_v21 import DirectionalTransfer, SemanticPlanV21
from src.experiments.semantic_contract_v21_evaluator import evaluate_v21_predictions


def test_v21_evaluator_does_not_score_generic_comparison_as_hcx_relation(tmp_path: Path) -> None:
    row = {
        "source_question_id": "Q-1", "question": "DB와 DC의 운용 주체 차이를 비교해줘",
        "subjects": ["account:DB", "account:DC"], "fields": ["operation_party"],
        "essential_qualifiers": [], "relations": [{"type": "comparison", "source": None, "destination": None, "left": None, "right": None}],
    }
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    score = evaluate_v21_predictions(path, {"Q-1": SemanticPlanV21(("account:DB", "account:DC"), ("operation_party",), (), ())})

    assert score["component_metrics"]["directional_transfers"]["f1"] == 0.0
    assert score["semantic_requirement_coverage"]["recall"] == 1.0
    assert score["requirement_exact"]["accuracy"] == 1.0


def test_v21_evaluator_counts_directional_transfer_miss(tmp_path: Path) -> None:
    # The full gold fixture is tested via a compact row because only transfer
    # endpoints, not generic comparison, are HCX relation obligations.
    row = {
        "source_question_id": "Q-2", "question": "ISA 만기 자금을 연금계좌로 옮겨요",
        "subjects": ["account:ISA", "account:pension"], "fields": ["transfer_deadline"],
        "essential_qualifiers": ["isa_maturity"],
        "relations": [{"type": "transfer", "source": "account:ISA", "destination": "account:pension", "left": None, "right": None}],
    }
    path = tmp_path / "transfer_gold.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    score = evaluate_v21_predictions(path, {"Q-2": SemanticPlanV21(("account:ISA", "account:pension"), ("transfer_deadline",), ("isa_maturity",), ())})

    assert score["component_metrics"]["directional_transfers"]["recall"] == 0.0
    assert score["real_semantic_miss_count"] == 1
