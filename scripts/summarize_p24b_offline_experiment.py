"""Summarize P24-B offline retrieval/matcher experiment artifacts.

This is evaluation-only.  It does not change the production agent, labels, or
retrieval index.  The four target sufficiency judgements are backed by the
P24-A source-to-corpus audit and the current selected chunks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


TARGET_REVIEW = {
    "R-010": {
        "owner": "evidence_matcher",
        "current_evidence_sufficient": True,
        "reason": "selected tax table contains the canonical unavoidable non-annuity withdrawal exception",
    },
    "R-024": {
        "owner": "retrieval_recall",
        "current_evidence_sufficient": True,
        "reason": "requirement query newly returns a same-product risk-grade table; the investment-target evidence was already selected",
    },
    "R-028": {
        "owner": "evidence_matcher",
        "current_evidence_sufficient": True,
        "reason": "same-product selected table states domestic-stock allocation and investment strategy, satisfying the target/strategy request",
    },
    "R-037": {
        "owner": "retrieval_recall",
        "current_evidence_sufficient": True,
        "reason": "DB/DC operation subqueries newly return the source comparison table",
    },
}


def _states(path: Path) -> dict[str, dict]:
    return {row["question_id"]: row for row in json.loads(path.read_text(encoding="utf-8"))["rows"]}


def _rows(path: Path) -> dict[str, dict]:
    return {row["question_id"]: row for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=ROOT / "data/diagnostics/p18_shared_shadow_preparation.json")
    parser.add_argument("--experiment", type=Path, default=ROOT / "data/diagnostics/p24b_full40_shared_preparation.json")
    parser.add_argument("--p15-baseline", type=Path, default=ROOT / "data/diagnostics/p19_mini_holdout_regression.jsonl")
    parser.add_argument("--p15-experiment", type=Path, default=ROOT / "evaluation/p24b_p15_mini_holdout_results.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p24b_offline_experiment.json")
    args = parser.parse_args()

    baseline, experiment = _states(args.baseline), _states(args.experiment)
    if set(baseline) != set(experiment):
        raise ValueError("Full-40 baseline and experiment IDs must match")
    target_rows = []
    for question_id, review in TARGET_REVIEW.items():
        before, after = baseline[question_id], experiment[question_id]
        target_rows.append(
            {
                "question_id": question_id,
                "primary_owner": review["owner"],
                "before": {
                    "gate_pass": before["evidence_sufficient"],
                    "missing_slots": before["missing_requirement_slots"],
                    "selected_chunk_ids": before["selected_merged_evidence_ids"],
                },
                "after": {
                    "gate_pass": after["evidence_sufficient"],
                    "missing_slots": after["missing_requirement_slots"],
                    "selected_chunk_ids": after["selected_merged_evidence_ids"],
                    "current_evidence_sufficient_review": review["current_evidence_sufficient"],
                },
                "review_reason": review["reason"],
            }
        )
    changed = []
    for question_id in baseline:
        before, after = baseline[question_id], experiment[question_id]
        fields = [
            field
            for field in (
                "candidate_chunk_ids",
                "selected_merged_evidence_ids",
                "evidence_sufficient",
                "gate_decision",
                "missing_requirement_slots",
            )
            if before[field] != after[field]
        ]
        if fields:
            changed.append(
                {
                    "question_id": question_id,
                    "changed_fields": fields,
                    "candidate_count": [len(before["candidate_chunk_ids"]), len(after["candidate_chunk_ids"])],
                    "selected_context_count": [len(before["selected_merged_evidence_ids"]), len(after["selected_merged_evidence_ids"])],
                }
            )
    p15_before, p15_after = _rows(args.p15_baseline), _rows(args.p15_experiment)
    if set(p15_before) != set(p15_after):
        raise ValueError("P15 baseline and experiment IDs must match")
    p15_route_or_gate_regressions = [
        question_id
        for question_id in p15_before
        if (p15_before[question_id]["predicted_route"], p15_before[question_id]["gate_pass"])
        != (p15_after[question_id]["predicted_route"], p15_after[question_id]["gate_pass"])
    ]
    payload = {
        "experiment": "P24-B offline requirement retrieval and canonical matcher",
        "hcx_called": False,
        "production_agent_changed": False,
        "full40_shared_preparation_parity": experiment["R-001"]["shared_preparation_parity"] and all(
            row["shared_preparation_parity"] for row in experiment.values()
        ),
        "target_cases": target_rows,
        "full40_context_impact": {
            "changed_questions": changed,
            "candidate_count": [
                sum(len(row["candidate_chunk_ids"]) for row in baseline.values()),
                sum(len(row["candidate_chunk_ids"]) for row in experiment.values()),
            ],
            "selected_context_count": [
                sum(len(row["selected_merged_evidence_ids"]) for row in baseline.values()),
                sum(len(row["selected_merged_evidence_ids"]) for row in experiment.values()),
            ],
        },
        "p15_mini_holdout": {
            "route_or_gate_regressions": p15_route_or_gate_regressions,
            "regression_free": not p15_route_or_gate_regressions,
        },
        "decision": "candidate_for_follow_up_review",
        "caveat": "P11's old partial/none labels for R-010, R-028, and R-037 describe the old candidate sets. They are not valid ground truth for the new current-evidence gate judgement and were not overwritten.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"targets_passing": sum(row["after"]["gate_pass"] for row in target_rows), "p15_regression_free": not p15_route_or_gate_regressions}, ensure_ascii=False))


if __name__ == "__main__":
    main()
