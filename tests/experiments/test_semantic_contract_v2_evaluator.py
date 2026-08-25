import json
from pathlib import Path

from src.experiments.semantic_contract_v2 import SemanticPlanV2, SemanticRelation
from src.experiments.semantic_contract_v2_evaluator import evaluate_v2_predictions


ROOT = Path(__file__).resolve().parents[2]


def test_v2_evaluator_scores_essential_qualifier_and_relation_coverage() -> None:
    gold = ROOT / "question_bank/development/semantic_contract_v2_manual_gold.jsonl"
    rows = [json.loads(line) for line in gold.read_text(encoding="utf-8").splitlines() if line]
    plans = {
        row["source_question_id"]: SemanticPlanV2(
            tuple(row["subjects"]), tuple(row["fields"]), tuple(row["essential_qualifiers"]),
            tuple(SemanticRelation(**relation) for relation in row["relations"]),
        )
        for row in rows
    }

    result = evaluate_v2_predictions(gold, plans)

    assert result["component_metrics"]["essential_qualifiers"]["f1"] == 1.0
    assert result["component_metrics"]["relations"]["f1"] == 1.0
    assert result["semantic_requirement_coverage"]["recall"] == 1.0
    assert result["requirement_exact"]["accuracy"] == 1.0
