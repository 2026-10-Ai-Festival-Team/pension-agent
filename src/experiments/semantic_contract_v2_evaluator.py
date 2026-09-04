"""Metrics for P38-6 isolated semantic-contract-v2 parsers."""
from __future__ import annotations

import json
from pathlib import Path

from src.experiments.semantic_contract_v2 import RequirementComposerV2, SemanticPlanV2, SemanticRelation


ROOT = Path(__file__).resolve().parents[2]


def _prf(predicted, gold):
    tp = fp = fn = 0
    for predicted_set, gold_set in zip(predicted, gold):
        tp += len(predicted_set & gold_set)
        fp += len(predicted_set - gold_set)
        fn += len(gold_set - predicted_set)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0}


def _relation_set(relations):
    return {f"{item.type}|{item.source or ''}|{item.destination or ''}|{item.left or ''}|{item.right or ''}" for item in relations}


def _gold_plan(row: dict) -> SemanticPlanV2:
    return SemanticPlanV2(
        tuple(row["subjects"]), tuple(row["fields"]), tuple(row["essential_qualifiers"]),
        tuple(SemanticRelation(**relation) for relation in row["relations"]),
    )


def evaluate_v2_predictions(gold_path: Path, predictions: dict[str, SemanticPlanV2]) -> dict:
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gold = [_gold_plan(row) for row in rows]
    predicted = [predictions.get(row["source_question_id"], SemanticPlanV2((), (), (), ())) for row in rows]
    metrics = {
        "subjects": _prf([set(plan.subjects) for plan in predicted], [set(plan.subjects) for plan in gold]),
        "fields": _prf([set(plan.fields) for plan in predicted], [set(plan.fields) for plan in gold]),
        "essential_qualifiers": _prf([set(plan.qualifiers) for plan in predicted], [set(plan.qualifiers) for plan in gold]),
        "relations": _prf([_relation_set(plan.relations) for plan in predicted], [_relation_set(plan.relations) for plan in gold]),
    }
    details, exact, covered, required, unsupported_extra = [], 0, 0, 0, 0
    for row, expected, actual in zip(rows, gold, predicted):
        gold_requirements = set(RequirementComposerV2.compose(expected))
        try:
            predicted_requirements = set(RequirementComposerV2.compose(actual))
        except ValueError:
            predicted_requirements = set()
        overlap = gold_requirements & predicted_requirements
        exact += int(gold_requirements == predicted_requirements)
        covered += len(overlap)
        required += len(gold_requirements)
        extra = (
            len(set(actual.subjects) - set(expected.subjects))
            + len(set(actual.fields) - set(expected.fields))
            + len(set(actual.qualifiers) - set(expected.qualifiers))
            + len(_relation_set(actual.relations) - _relation_set(expected.relations))
        )
        unsupported_extra += extra
        details.append({
            "source_question_id": row["source_question_id"],
            "gold": {"subjects": list(expected.subjects), "fields": list(expected.fields), "essential_qualifiers": list(expected.qualifiers), "relations": [item.__dict__ for item in expected.relations]},
            "predicted": {"subjects": list(actual.subjects), "fields": list(actual.fields), "essential_qualifiers": list(actual.qualifiers), "relations": [item.__dict__ for item in actual.relations]},
            "gold_requirements": sorted(gold_requirements),
            "predicted_requirements": sorted(predicted_requirements),
            "semantic_requirement_coverage": round(len(overlap) / len(gold_requirements), 4) if gold_requirements else 1.0,
            "requirement_exact": gold_requirements == predicted_requirements,
            "unsupported_extra_atoms": extra,
        })
    return {
        "question_count": len(rows),
        "component_metrics": metrics,
        "semantic_requirement_coverage": {"matched_requirements": covered, "gold_requirements": required, "recall": round(covered / required, 4) if required else 1.0},
        "requirement_exact": {"exact": exact, "total": len(rows), "accuracy": round(exact / len(rows), 4) if rows else 0.0},
        "unsupported_extra_atoms": unsupported_extra,
        "details": details,
    }
