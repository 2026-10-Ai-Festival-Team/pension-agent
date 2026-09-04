"""Run the one-record P49-2H-4D-E2A supported-answer completeness retest."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_e_register_tranche as register_builder
from scripts import build_p49_2h_4d_e2a_supported_answer_repair as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk


DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_manifest_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_audit_v1.json"


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2A answer-repair artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError("E2A requires exactly one same-record retest")
    row = rows[0]
    if row.get("remediation_request_id") != "P49-2H-4D-E2A-ETF-0001":
        raise ValueError("E2A does not accept another remediation request ID")
    if row.get("canonical_requirement") != builder.TARGET_REQUIREMENT or row.get("target_outcome") != "supported_answer":
        raise ValueError("E2A is limited to the IRP ETF supported requirement")
    if not row.get("supported_answer_completeness"):
        raise ValueError("E2A completeness binding is missing")
    return row


def audit(row: dict[str, Any], trace: dict[str, Any], candidate: dict[str, Any] | None, current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [] if candidate is None else [candidate]
    findings = list(trace.get("validation_findings", []))
    classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - bulk.KNOWN_FAILURE_CLASSES)
    dedup = bridge.full_set_dedup_audit(current_pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    bridge_healthy = (
        trace["caller_input_preservation_pass"]
        and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"]
        and trace["external_call_success"]
        and trace["response_schema_valid"]
        and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success"
        and trace["validator_executed"]
    )
    prohibited = (
        "supported_required_fact_omission",
        "supported_adjacent_field_expansion",
        "supported_unsupported_caveat_expansion",
        "subject_provenance_mismatch",
    )
    clean = candidate is not None and candidate.get("validation_status") == "pass" and not any(
        finding in findings for finding in prohibited
    )
    return {
        "stage": "P49-2H-4D-E2A Supported Answer Omission Repair",
        "external_hcx_calls": trace["attempt_count"],
        "comparison_pool_before": len(current_pool),
        "target_requirement": builder.TARGET_REQUIREMENT,
        "same_host_question": candidate.get("question") if candidate else None,
        "model_question_raw": candidate.get("model_question_raw") if candidate else None,
        "generation_status": trace["generation_status"],
        "bridge_schema_hydration_validator_normal": bridge_healthy,
        "validation_status": trace["validation_status"],
        "validation_findings": findings,
        "target_omission_zero": "supported_required_fact_omission" not in findings,
        "adjacent_field_expansion_zero": "supported_adjacent_field_expansion" not in findings,
        "unsupported_fact_expansion_zero": "supported_unsupported_caveat_expansion" not in findings,
        "subject_provenance_drift_zero": "subject_provenance_mismatch" not in findings,
        "new_failure_classes": new_failure_classes,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "e2a_answer_completeness_go": bridge_healthy and clean and not new_failure_classes and collisions == 0,
        "initial_e_candidate_promotion_held": True,
        "e1_candidate_promotion_held": True,
        "e2_candidate_promotion_held": True,
        "e2a_candidate_promotion_held": True,
        "neighbor_smoke_allowed": bridge_healthy and clean and not new_failure_classes and collisions == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for the one E2A record.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--max-generation-attempts", type=int, default=1)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; E2A build/preflight makes zero HCX calls")
    if args.max_generation_attempts != 1:
        parser.error("E2A same-record retest intentionally permits exactly one generation attempt")
    rows = bridge.read_jsonl(args.manifest)
    row = validate_manifest(rows)
    current_pool, _ = register_builder.current_quality_pool()
    preflight_report = builder.preflight(row, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    if not preflight_report["live_execution_allowed"] or preflight_report["comparison_pool_pass"] != 435:
        parser.error("E2A preflight failed or comparison pool is not fixed at 435; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live E2A artifact already exists; choose a new path: {path}")
    generator = bridge.configured_generator()
    corpus = {item["chunk_id"]: item for item in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [item["question"] for item in bridge.read_jsonl(bridge.FROZEN_SEED)]
    adapted = bridge.adapt_remediation_record(row, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS))
    trace, candidate = bridge.execute_adapted_request(
        row, adapted, mode="supported-answer-repair", generator=generator, corpus=corpus,
        seed_questions=seed_questions, comparison_questions=[item["question"] for item in current_pool],
        max_generation_attempts=1,
    )
    bridge.append_jsonl(args.trace_output, [trace])
    if candidate is not None:
        bridge.append_jsonl(args.candidate_output, [candidate])
    report = audit(row, trace, candidate, current_pool)
    write_new_json(args.audit_output, report)
    print(json.dumps({
        key: report[key]
        for key in (
            "external_hcx_calls", "target_requirement", "generation_status", "validation_status",
            "target_omission_zero", "e2a_answer_completeness_go", "neighbor_smoke_allowed",
        )
    } | {"audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
