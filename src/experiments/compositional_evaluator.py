"""Metrics for the isolated P38-1 semantic atom experiment."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from src.experiments.compositional_canonicalizer import CompositionalParser, RequirementComposer, SemanticAtoms


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLD = ROOT / "question_bank/development/semantic_atoms_v1.jsonl"


def _prf(predicted: Iterable[set[str]], gold: Iterable[set[str]]) -> dict[str, float | int]:
    true_positive = false_positive = false_negative = 0
    for predicted_set, gold_set in zip(predicted, gold):
        true_positive += len(predicted_set & gold_set)
        false_positive += len(predicted_set - gold_set)
        false_negative += len(gold_set - predicted_set)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def evaluate_predictions(gold_path: Path, predictions: dict[str, object]) -> dict:
    """Score externally produced SemanticAtoms against the same canonical gold."""
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prediction_rows = [predictions.get(row["source_question_id"], SemanticAtoms((), (), (), ())) for row in rows]
    components = ("subjects", "actions", "fields", "modifiers")
    metrics = {
        component: _prf(
            [set(getattr(prediction, component)) for prediction in prediction_rows],
            [set(row[component]) for row in rows],
        )
        for component in components
    }
    exact = 0
    details = []
    for row, prediction in zip(rows, prediction_rows):
        predicted_requirements = set(RequirementComposer.compose(prediction))
        # Gold lists encode sets of canonical atoms.  Re-compose them with the
        # same canonical ordering as predictions: requirement semantics must
        # not fail merely because DB+DC or manage+compare was written in a
        # different list order in the annotation file.
        gold_atoms = SemanticAtoms(
            tuple(sorted(row["subjects"])),
            tuple(sorted(row["actions"])),
            tuple(sorted(row["fields"])),
            tuple(sorted(row["modifiers"])),
        )
        gold_requirements = set(RequirementComposer.compose(gold_atoms))
        matches = predicted_requirements == gold_requirements
        exact += int(matches)
        details.append({
            "id": row["id"],
            "source_question_id": row["source_question_id"],
            "predicted": asdict(prediction),
            "gold": {key: row[key] for key in components},
            "predicted_requirements": sorted(predicted_requirements),
            "gold_requirements": sorted(gold_requirements),
            "requirement_exact": matches,
        })
    multi_field_rows = [
        (row, prediction)
        for row, prediction in zip(rows, prediction_rows)
        if len(row["fields"]) >= 2
    ]
    multi_field_hits = sum(len(set(row["fields"]) & set(prediction.fields)) for row, prediction in multi_field_rows)
    multi_field_total = sum(len(row["fields"]) for row, _ in multi_field_rows)
    return {
        "experiment": "P38-1 isolated compositional parser",
        "candidate_agent_changed": False,
        "gold_path": str(gold_path.relative_to(ROOT)) if gold_path.is_relative_to(ROOT) else str(gold_path),
        "question_count": len(rows),
        "component_metrics": metrics,
        "requirement_composition": {
            "exact": exact,
            "total": len(rows),
            "accuracy": round(exact / len(rows), 4) if rows else 0.0,
        },
        "multi_atom_field_recall": {
            "true_positive": multi_field_hits,
            "gold_total": multi_field_total,
            "recall": round(multi_field_hits / multi_field_total, 4) if multi_field_total else 0.0,
        },
        "details": details,
    }


def evaluate(parser: CompositionalParser | None = None, gold_path: Path = DEFAULT_GOLD) -> dict:
    """Evaluate a deterministic parser with order-independent canonical sets."""
    parser = parser or CompositionalParser()
    rows = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return evaluate_predictions(gold_path, {row["source_question_id"]: parser.parse(row["question"]) for row in rows})
