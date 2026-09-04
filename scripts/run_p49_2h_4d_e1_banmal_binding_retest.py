"""Run the fixed twelve-record P49-2H-4D-E1 banmal binding smoke.

Only supported and clarification questions are model-authored here.  This is
not a bulk remediation route and never promotes candidates automatically.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_e_register_tranche as register_builder
from scripts import build_p49_2h_4d_e1_banmal_binding_retest as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts import run_p49_2h_4d_e_register_tranche as register_runner


DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_manifest_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_audit_v1.json"


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E1 binding-retest artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 12:
        raise ValueError(f"E1 banmal binding retest must have exactly 12 rows; found {len(rows)}")
    allocation = Counter((row.get("target_outcome"), row.get("register")) for row in rows)
    if allocation != builder.EXPECTED_ALLOCATION:
        raise ValueError(f"unexpected E1 lane/register allocation: {dict(allocation)}")
    if any(row.get("target_outcome") == "bounded_answer" for row in rows):
        raise ValueError("E1 banmal binding retest excludes bounded_answer")
    if any(row.get("noise_style") != "none" for row in rows):
        raise ValueError("E1 banmal binding retest must keep noise_style=none")
    if len({row.get("remediation_request_id") for row in rows}) != len(rows):
        raise ValueError("E1 banmal binding retest request IDs must be unique")
    if len({row.get("banmal_retest_source_request_id") for row in rows}) != len(rows):
        raise ValueError("E1 banmal binding retest source request IDs must be unique")


def audit(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    pass_candidates = [row for row in candidates if row.get("validation_status") == "pass"]
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - bulk.KNOWN_FAILURE_CLASSES)
    dedup = bridge.full_set_dedup_audit(current_pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    bridge_healthy = len(traces) == len(selected) and all(
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
    styles = register_runner.style_audit(selected, traces, candidates)
    aggregate = register_runner.finding_metrics(traces)
    strict_clean = (
        len(pass_candidates) == len(selected)
        and not any(trace["generation_status"] == "generation_exhausted" for trace in traces)
        and aggregate == {
            "semantic_drift": 0,
            "omission": 0,
            "near_duplicate": 0,
            "subject_loss": 0,
            "register_surface_drift": 0,
        }
    )
    e1_go = bridge_healthy and strict_clean and not new_failure_classes and collision_count == 0
    return {
        "stage": "P49-2H-4D-E1 Supported/Clarification Banmal Binding Retest",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "comparison_pool_before": len(current_pool),
        "requested": len(selected),
        "requested_by_register": dict(Counter(row["register"] for row in selected)),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in selected)),
        "requested_by_lane_and_register": {
            f"{lane}:{register}": count
            for (lane, register), count in sorted(Counter((row["target_outcome"], row["register"]) for row in selected).items())
        },
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(pass_candidates),
        "bridge_schema_hydration_validator_12_of_12": bridge_healthy,
        "style_metrics": styles,
        "aggregate_binding_and_quality_metrics": aggregate,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "initial_e_candidate_promotion_held": True,
        "e1_pass_candidate_promotion_held": True,
        "comparison_pool_if_e1_promoted": len(current_pool) + len(pass_candidates),
        "register_binding_retest_go": e1_go,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for this exact 12-record E1 smoke.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    parser.add_argument("--audit-existing", action="store_true", help="Local-only audit; requires trace and candidate inputs.")
    parser.add_argument("--existing-trace", type=Path)
    parser.add_argument("--existing-candidates", type=Path)
    args = parser.parse_args()
    if args.audit_existing:
        if args.live or not args.existing_trace or not args.existing_candidates:
            parser.error("--audit-existing is local-only and requires --existing-trace plus --existing-candidates")
    elif not args.live:
        parser.error("--live is required; build/preflight is the zero-HCX E1 step")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")

    selected = bridge.read_jsonl(args.manifest)
    validate_manifest(selected)
    current_pool, _ = register_builder.current_quality_pool()
    preflight_report = builder.preflight(selected, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    if not preflight_report["live_execution_allowed"] or preflight_report["comparison_pool_pass"] != 435:
        parser.error("E1 preflight failed or comparison pool is not fixed at 435; no HCX call was made")

    if args.audit_existing:
        traces = bridge.read_jsonl(args.existing_trace)
        candidates = bridge.read_jsonl(args.existing_candidates)
        expected_ids = {row["remediation_request_id"] for row in selected}
        if {row.get("remediation_request_id") for row in traces} != expected_ids:
            parser.error("existing trace does not match the fixed 12-row E1 manifest")
        report = audit(selected, traces, candidates, current_pool)
        write_new_json(args.audit_output, report)
        print(json.dumps({
            "external_hcx_calls": 0,
            "requested": report["requested"],
            "semantic_evidence_outcome_pass": report["semantic_evidence_outcome_pass"],
            "register_binding_retest_go": report["register_binding_retest_go"],
            "audit_output": str(args.audit_output),
        }, ensure_ascii=False))
        return

    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live E1 artifact already exists; choose a new path: {path}")

    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    comparison_questions = [row["question"] for row in current_pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in selected:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row,
            adapted,
            mode="register-retest",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["register_binding_version"] = row["register_binding_version"]
        trace["banmal_retest_source_request_id"] = row["banmal_retest_source_request_id"]
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidate["register_binding_version"] = row["register_binding_version"]
            candidate["banmal_retest_source_request_id"] = row["banmal_retest_source_request_id"]
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
            "comparison_pool_before",
            "requested",
            "semantic_evidence_outcome_pass",
            "generation_exhausted",
            "bridge_schema_hydration_validator_12_of_12",
            "register_binding_retest_go",
        )
    } | {"style_metrics": report["style_metrics"], "audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
