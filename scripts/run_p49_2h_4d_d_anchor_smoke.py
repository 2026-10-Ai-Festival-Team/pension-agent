"""Run the approved, anchor-only eight-record P49-2H-4D-D smoke.

This runner keeps the linguistic-anchor experiment separate from the later
register-taxonomy experiment.  It selects exactly two reviewed anchors from
each of D12-Q12, D17-Q17, D18-Q18, and D20-Q12; it refuses any new banmal
register in this run.  All live calls reuse the guarded 4C bridge, canonical
v4 candidate construction, hydration, and validator.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_bounded_targeted_v6 as v6
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts.p49_2h_register_taxonomy import REGISTER_RULES
from scripts.run_p49_2h_full_adapter import semantic_question_findings


APPROVED_ANCHORS = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_human_approved_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_audit_v1.json"
DEFAULT_PREFLIGHT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_preflight_v1.json"
TARGET_CELLS = (
    "D12-Q12-bounded_answer",
    "D17-Q17-bounded_answer",
    "D18-Q18-bounded_answer",
    "D20-Q12-bounded_answer",
)
PER_CELL = 2
REGISTER_EXPERIMENT_VALUES = frozenset({"formal", "polite", "casual_banmal", "terse_banmal"})


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite anchor-smoke artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_anchor_smoke(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Choose the first two ordered human-approved anchors from every target cell."""
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("coverage_cell") in TARGET_CELLS:
            by_cell[row["coverage_cell"]].append(row)
    selected: list[dict[str, Any]] = []
    for cell in TARGET_CELLS:
        cell_rows = sorted(by_cell[cell], key=lambda row: row["remediation_request_id"])
        if len(cell_rows) != 3:
            raise ValueError(f"expected exactly three approved anchors for {cell}; found {len(cell_rows)}")
        selected.extend(cell_rows[:PER_CELL])
    if len(selected) != len(TARGET_CELLS) * PER_CELL:
        raise AssertionError("anchor-smoke selection is not exactly eight records")
    ids = [row["remediation_request_id"] for row in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("anchor-smoke selection contains duplicate request IDs")
    return selected


def preflight(
    selected: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    current_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed before HCX on review, preservation, prompt, and dedup gates."""
    failures: list[dict[str, Any]] = []
    for row in selected:
        try:
            anchor = row.get("bounded_linguistic_anchor", {})
            if (
                anchor.get("authoring_status") != "human_written"
                or anchor.get("human_review_status") != "human_approved"
            ):
                failures.append({"remediation_request_id": row["remediation_request_id"], "anchor_review": "not_human_written_and_approved"})
                continue
            if row.get("register") in REGISTER_EXPERIMENT_VALUES:
                failures.append({"remediation_request_id": row["remediation_request_id"], "register_experiment": row["register"]})
                continue
            if row.get("register") not in REGISTER_RULES:
                failures.append({"remediation_request_id": row["remediation_request_id"], "unsupported_register": row.get("register")})
                continue
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            semantic = semantic_question_findings(anchor["anchor_question"], adapted["semantic_request"])
            if preservation or diversity or boundary or semantic:
                failures.append(
                    {
                        "remediation_request_id": row["remediation_request_id"],
                        "preservation_findings": preservation,
                        "diversity_prompt_findings": diversity,
                        "field_boundary_prompt_findings": boundary,
                        "anchor_semantic_findings": semantic,
                    }
                )
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    preflight_inputs = [
        {
            "remediation_request_id": row["remediation_request_id"],
            "validation_status": "pass",
            "generation_status": "not_generated_human_approved_anchor_smoke",
            "question": row["bounded_linguistic_anchor"]["anchor_question"],
        }
        for row in selected
    ]
    dedup = bridge.full_set_dedup_audit(current_pool, preflight_inputs, bridge.read_jsonl(bridge.FROZEN_SEED))
    dedup_collisions = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    return {
        "stage": "P49-2H-4D-D approved anchor smoke preflight",
        "external_hcx_calls": 0,
        "requested": len(selected),
        "requested_by_cell": {cell: sum(row["coverage_cell"] == cell for row in selected) for cell in TARGET_CELLS},
        "register_taxonomy_experiment_applied": False,
        "human_written_human_approved": sum(
            row["bounded_linguistic_anchor"]["authoring_status"] == "human_written"
            and row["bounded_linguistic_anchor"]["human_review_status"] == "human_approved"
            for row in selected
        ),
        "preservation_prompt_and_semantic_pass": len(selected) - len(failures),
        "failures": failures,
        "anchor_full_set_dedup": dedup,
        "anchor_full_set_dedup_pass": dedup_collisions == 0,
        "live_execution_allowed": not failures and dedup_collisions == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def current_quality_pool() -> list[dict[str, Any]]:
    immutable = [row for row in bridge.read_jsonl(bridge.COMPARISON_POOL) if row.get("validation_status") == "pass"]
    promoted = v6.promoted_passes(v6.read_many(list(v6.DEFAULT_CANDIDATES)))
    if len(immutable) != 133 or len(promoted) != 294:
        raise ValueError(f"expected current quality pool 133 + 294; found {len(immutable)} + {len(promoted)}")
    return [*immutable, *promoted.values()]


def audit(
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    current_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    """Report bridge health separately from the anchor-space outcome."""
    pass_candidates = [row for row in candidates if row.get("validation_status") == "pass"]
    pass_by_cell = Counter(row["coverage_cell"] for row in pass_candidates)
    trace_by_cell = Counter(trace["coverage_cell"] for trace in traces)
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    finding_classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(finding_classes - bulk.KNOWN_FAILURE_CLASSES)
    full_dedup = bridge.full_set_dedup_audit(current_pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(full_dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    d17_unique_pass = pass_by_cell["D17-Q17-bounded_answer"]
    bridge_healthy = all(
        trace["caller_input_preservation_pass"]
        and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"]
        and trace["external_call_success"]
        and trace["response_schema_valid"]
        and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success"
        and trace["validator_executed"]
        for trace in traces
    )
    return {
        "stage": "P49-2H-4D-D Linguistic Anchor Smoke",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "requested": len(selected),
        "requested_by_cell": {cell: trace_by_cell[cell] for cell in TARGET_CELLS},
        "register_taxonomy_experiment_applied": False,
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(pass_candidates),
        "pass_by_cell": {cell: pass_by_cell[cell] for cell in TARGET_CELLS},
        "d17_unique_pass": d17_unique_pass,
        "human_anchor_space_hypothesis": "supported" if d17_unique_pass else "not_supported",
        # The canonical bounded bridge deliberately writes the reviewed anchor
        # as the final host-owned question.  HCX produces the structured
        # response that is hydrated and validated, but this smoke must not be
        # reported as an isolated test of model-authored question wording.
        "candidate_question_authority": "host_owned_human_approved_anchor",
        "hcx_generated_question_effect": "not_identifiable_in_host_owned_anchor_route",
        "caller_input_preservation_failures": [trace["remediation_request_id"] for trace in traces if not trace["caller_input_preservation_pass"]],
        "response_schema_failures": [trace["remediation_request_id"] for trace in traces if trace["response_schema_valid"] is False],
        "bridge_healthy": bridge_healthy,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "cumulative_full_set_dedup": full_dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "cumulative_quality_pool_before": len(current_pool),
        "promotion_eligible_pass_count": len(pass_candidates),
        "cumulative_quality_pool_if_promoted": len(current_pool) + len(pass_candidates),
        "promotion_allowed": bridge_healthy and d17_unique_pass > 0 and not new_failure_classes and collision_count == 0,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for the exact approved eight-record anchor smoke.")
    parser.add_argument("--input", type=Path, default=APPROVED_ANCHORS)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT_OUTPUT)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")

    selected = select_anchor_smoke(bridge.read_jsonl(args.input))
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    current_pool = current_quality_pool()
    preflight_report = preflight(selected, semantic_rows, current_pool)
    if not args.live:
        write_new_json(args.preflight_output, preflight_report)
        print(json.dumps({
            "external_hcx_calls": 0,
            "requested": preflight_report["requested"],
            "preflight_pass": preflight_report["preservation_prompt_and_semantic_pass"],
            "dedup_pass": preflight_report["anchor_full_set_dedup_pass"],
            "live_execution_allowed": preflight_report["live_execution_allowed"],
            "preflight_output": str(args.preflight_output),
        }, ensure_ascii=False))
        return
    if not preflight_report["live_execution_allowed"]:
        parser.error("anchor-smoke preflight failed; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live anchor-smoke artifact already exists; choose a new path: {path}")

    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    comparison_questions = [row["question"] for row in current_pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in selected:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row,
            adapted,
            mode="anchor-smoke",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["register_taxonomy_experiment_applied"] = False
        trace["anchor_smoke_cell"] = row["coverage_cell"]
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])

    report = audit(selected, traces, candidates, current_pool)
    write_new_json(args.audit_output, report)
    print(json.dumps({
        key: report[key]
        for key in (
            "external_hcx_calls",
            "requested",
            "semantic_evidence_outcome_pass",
            "d17_unique_pass",
            "human_anchor_space_hypothesis",
            "bridge_healthy",
            "promotion_allowed",
        )
    } | {"trace_output": str(args.trace_output), "candidate_output": str(args.candidate_output), "audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
