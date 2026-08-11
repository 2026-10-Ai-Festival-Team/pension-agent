"""P13 holdout에서 frozen experimental Router/Gate를 HCX 없이 평가한다."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever


def _load_items(path: Path, key: str) -> dict[str, dict]:
    return {item["question_id"]: item for item in json.loads(path.read_text(encoding="utf-8"))[key]}


def _safe_rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def _route_metrics(rows: list[dict]) -> dict:
    routes = ("simple", "compound", "unsupported")
    confusion = {
        gold: {predicted: 0 for predicted in routes}
        for gold in routes
    }
    for row in rows:
        confusion[row["gold_route"]][row["predicted_route"]] += 1
    per_route = {}
    for route in routes:
        true_positive = confusion[route][route]
        predicted_total = sum(confusion[gold][route] for gold in routes)
        actual_total = sum(confusion[route].values())
        per_route[route] = {
            "precision": _safe_rate(true_positive, predicted_total),
            "recall": _safe_rate(true_positive, actual_total),
        }
    return {
        "accuracy": _safe_rate(
            sum(row["route_correct"] for row in rows), len(rows)
        ),
        "confusion_matrix": confusion,
        "per_route": per_route,
        "simple_to_compound": confusion["simple"]["compound"],
        "compound_to_simple": confusion["compound"]["simple"],
        "supported_to_unsupported": sum(confusion[route]["unsupported"] for route in ("simple", "compound")),
        "unsupported_to_supported": sum(confusion["unsupported"][route] for route in ("simple", "compound")),
    }


def _gate_metrics(rows: list[dict]) -> dict:
    correct_pass = sum(row["evidence_sufficient_expected"] and row["gate_pass"] for row in rows)
    false_rejection = sum(row["evidence_sufficient_expected"] and not row["gate_pass"] for row in rows)
    correct_rejection = sum(not row["evidence_sufficient_expected"] and not row["gate_pass"] for row in rows)
    unsafe_pass = sum(not row["evidence_sufficient_expected"] and row["gate_pass"] for row in rows)
    return {
        "correct_pass": correct_pass,
        "false_rejection": false_rejection,
        "correct_rejection": correct_rejection,
        "unsafe_pass": unsafe_pass,
        "false_rejection_rate": _safe_rate(false_rejection, correct_pass + false_rejection),
        "unsafe_pass_rate": _safe_rate(unsafe_pass, correct_rejection + unsafe_pass),
    }


def _entity_metrics(rows: list[dict]) -> dict:
    expected = extracted = matched = 0
    false_positive = 0
    for row in rows:
        expected_set = set(row["required_entities"])
        extracted_set = set(row["extracted_entities"])
        expected += len(expected_set)
        extracted += len(extracted_set)
        matched += len(expected_set & extracted_set)
        false_positive += len(extracted_set - expected_set)
    return {
        "precision": _safe_rate(matched, extracted),
        "recall": _safe_rate(matched, expected),
        "false_positive": false_positive,
    }


def _slot_metrics(rows: list[dict]) -> dict:
    compound_rows = [row for row in rows if row["gold_route"] == "compound"]
    expected_count = sum(len(row["required_slot_keys"]) for row in compound_rows)
    matched_count = sum(
        len(set(row["required_slot_keys"]) & set(row["generated_slot_keys"]))
        for row in compound_rows
    )
    missing_count = sum(
        len(set(row["required_slot_keys"]) - set(row["generated_slot_keys"]))
        for row in compound_rows
    )
    spurious_count = sum(
        len(set(row["generated_slot_keys"]) - set(row["required_slot_keys"]))
        for row in compound_rows
    )
    return {
        "required_slot_count": expected_count,
        "matched_slot_count": matched_count,
        "required_slot_recall": _safe_rate(matched_count, expected_count),
        "missing_slot_count": missing_count,
        "spurious_slot_count": spurious_count,
    }


def _primary_owner(
    label: dict,
    route_correct: bool,
    gate_pass: bool,
    generated_slot_keys: list[str],
) -> str:
    if not route_correct:
        return "router"
    if label["evidence_sufficient_expected"] and not gate_pass:
        return "requirement_template_or_gate" if not generated_slot_keys else "slot_matcher_or_retrieval"
    if not label["evidence_sufficient_expected"] and gate_pass:
        return "gate"
    if not set(label.get("required_slot_keys", [])) <= set(generated_slot_keys):
        return "requirement_template_or_gate"
    return "none"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/p13_holdout_questions.json")
    parser.add_argument("--labels", type=Path, default=ROOT / "evaluation/p13_holdout_labels.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p13_holdout_results.jsonl")
    args = parser.parse_args()

    questions = _load_items(args.questions, "questions")
    labels = _load_items(args.labels, "labels")
    if set(questions) != set(labels):
        raise ValueError("P13 question and label IDs must match exactly")

    analyzer = QueryAnalyzer()
    router = ExperimentalRouter()
    gate = ExperimentalRouteGate()
    retriever = build_frozen_retriever(args.corpus, args.index)
    rows = []
    for question_id, question in questions.items():
        label = labels[question_id]
        if label["label_status"] != "adjudicated":
            continue
        analysis = analyzer.analyze(question["question"])
        route = router.classify(analysis)
        results = retriever.search(question["question"], top_k=10).results
        generated_case = route.requirement_case
        decision = gate.assess(route.route, analysis, results, generated_case)
        generated_slots = [slot.name for slot in generated_case.slots] if generated_case else []
        generated_slot_keys = [
            slot.key or slot.name.replace(" ", ":", 1)
            for slot in (generated_case.slots if generated_case else ())
        ]
        extracted_entities = list(analysis.extracted_entities.accounts) + list(analysis.product_codes)
        row = {
            "question_id": question_id,
            "question": question["question"],
            "gold_route": label["gold_route"],
            "predicted_route": route.route,
            "route_correct": route.route == label["gold_route"],
            "route_reasons": route.reasons,
            "required_domains": label["required_domains"],
            "required_entities": label["required_entities"],
            "extracted_entities": extracted_entities,
            "required_evidence_slots": label["required_evidence_slots"],
            "required_slot_keys": label.get("required_slot_keys", []),
            "generated_evidence_slots": generated_slots,
            "generated_slot_keys": generated_slot_keys,
            "evidence_sufficient_expected": label["evidence_sufficient_expected"],
            "expected_gate": label["expected_gate"],
            "gate_pass": decision.sufficient,
            "gate_decision": decision.reason,
            "missing_slots": decision.missing_slots,
            "selected_chunk_ids": decision.selected_chunk_ids,
            "retrieved_chunk_ids": [result.chunk_id for result in results],
        }
        row["primary_owner"] = _primary_owner(
            label, row["route_correct"], row["gate_pass"], generated_slot_keys
        )
        rows.append(row)

    summary = {
        "holdout_size": len(rows),
        "route_distribution": dict(Counter(row["gold_route"] for row in rows)),
        "routing": _route_metrics(rows),
        "gate": _gate_metrics(rows),
        "entity_extraction": _entity_metrics(rows),
        "requirement_slots": _slot_metrics(rows),
        "requirement_slot_cases": sum(bool(row["required_evidence_slots"]) for row in rows if row["gold_route"] == "compound"),
        "compound_with_generated_slots": sum(bool(row["generated_evidence_slots"]) for row in rows if row["gold_route"] == "compound"),
        "failure_owners": dict(Counter(row["primary_owner"] for row in rows)),
        "hcx_called": False,
    }
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
