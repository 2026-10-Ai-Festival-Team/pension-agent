"""P38-7B metrics for the v2.1 semantic contract."""
from __future__ import annotations

import json
from pathlib import Path

from src.experiments.semantic_contract_v21 import DirectionalTransfer, RequirementComposerV21, SemanticPlanV21


def _prf(predicted, gold):
    tp = fp = fn = 0
    for predicted_set, gold_set in zip(predicted, gold):
        tp += len(predicted_set & gold_set)
        fp += len(predicted_set - gold_set)
        fn += len(gold_set - predicted_set)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0}


def _transfer_set(transfers):
    return {f"{item.source}->{item.destination}" for item in transfers}


def project_v2_gold_to_v21(row: dict) -> SemanticPlanV21:
    """Remove generic comparison representation but retain directional transfer."""
    transfers = tuple(
        DirectionalTransfer(item["source"], item["destination"])
        for item in row["relations"]
        if item["type"] == "transfer"
    )
    return SemanticPlanV21(tuple(row["subjects"]), tuple(row["fields"]), tuple(row["essential_qualifiers"]), transfers)


def evaluate_v21_predictions(gold_path: Path, predictions: dict[str, SemanticPlanV21]) -> dict:
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gold = [project_v2_gold_to_v21(row) for row in rows]
    predicted = [predictions.get(row["source_question_id"], SemanticPlanV21((), (), (), ())) for row in rows]
    metrics = {
        "subjects": _prf([set(plan.subjects) for plan in predicted], [set(plan.subjects) for plan in gold]),
        "fields": _prf([set(plan.fields) for plan in predicted], [set(plan.fields) for plan in gold]),
        "essential_qualifiers": _prf([set(plan.qualifiers) for plan in predicted], [set(plan.qualifiers) for plan in gold]),
        "directional_transfers": _prf([_transfer_set(plan.transfers) for plan in predicted], [_transfer_set(plan.transfers) for plan in gold]),
    }
    details, exact, covered, required, extras, misses = [], 0, 0, 0, 0, 0
    for row, expected, actual in zip(rows, gold, predicted):
        gold_requirements = set(RequirementComposerV21.compose(row["question"], expected))
        try:
            predicted_requirements = set(RequirementComposerV21.compose(row["question"], actual))
        except ValueError:
            predicted_requirements = set()
        overlap = gold_requirements & predicted_requirements
        missed = {
            "subjects": sorted(set(expected.subjects) - set(actual.subjects)),
            "fields": sorted(set(expected.fields) - set(actual.fields)),
            "essential_qualifiers": sorted(set(expected.qualifiers) - set(actual.qualifiers)),
            "directional_transfers": sorted(_transfer_set(expected.transfers) - _transfer_set(actual.transfers)),
        }
        extra = {
            "subjects": sorted(set(actual.subjects) - set(expected.subjects)),
            "fields": sorted(set(actual.fields) - set(expected.fields)),
            "essential_qualifiers": sorted(set(actual.qualifiers) - set(expected.qualifiers)),
            "directional_transfers": sorted(_transfer_set(actual.transfers) - _transfer_set(expected.transfers)),
        }
        miss_count = sum(len(values) for values in missed.values())
        extra_count = sum(len(values) for values in extra.values())
        misses += miss_count
        extras += extra_count
        exact += int(gold_requirements == predicted_requirements)
        covered += len(overlap)
        required += len(gold_requirements)
        details.append({
            "source_question_id": row["source_question_id"],
            "question": row["question"],
            "gold": {"subjects": list(expected.subjects), "fields": list(expected.fields), "essential_qualifiers": list(expected.qualifiers), "directional_transfers": [item.__dict__ for item in expected.transfers]},
            "predicted": {"subjects": list(actual.subjects), "fields": list(actual.fields), "essential_qualifiers": list(actual.qualifiers), "directional_transfers": [item.__dict__ for item in actual.transfers]},
            "gold_requirements": sorted(gold_requirements),
            "predicted_requirements": sorted(predicted_requirements),
            "semantic_requirement_coverage": round(len(overlap) / len(gold_requirements), 4) if gold_requirements else 1.0,
            "requirement_exact": gold_requirements == predicted_requirements,
            "real_semantic_misses": missed,
            "real_semantic_miss_count": miss_count,
            "unsupported_extras": extra,
            "unsupported_extra_atom_count": extra_count,
        })
    return {
        "question_count": len(rows),
        "component_metrics": metrics,
        "semantic_requirement_coverage": {"matched_requirements": covered, "gold_requirements": required, "recall": round(covered / required, 4) if required else 1.0},
        "requirement_exact": {"exact": exact, "total": len(rows), "accuracy": round(exact / len(rows), 4) if rows else 0.0},
        "real_semantic_miss_count": misses,
        "unsupported_extra_atom_count": extras,
        "details": details,
    }
