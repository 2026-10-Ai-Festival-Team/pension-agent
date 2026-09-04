"""Run the fixed three-record P49-2H-4D-E2A neighbor smoke."""
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
from scripts import build_p49_2h_4d_e2a_supported_answer_neighbors as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk


DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_manifest_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_audit_v1.json"


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2A neighbor artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 3:
        raise ValueError("E2A neighbor smoke must contain exactly three rows")
    if any(row.get("target_outcome") != "supported_answer" for row in rows):
        raise ValueError("E2A neighbor smoke is supported-answer only")
    if any(row.get("supported_answer_completeness") is not None for row in rows):
        raise ValueError("E2A target-only binding must not appear in neighbors")
    if len({row.get("canonical_requirement") for row in rows}) != 3:
        raise ValueError("E2A neighbor smoke requires distinct supported requirements")


def audit(rows: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - bulk.KNOWN_FAILURE_CLASSES)
    dedup = bridge.full_set_dedup_audit(current_pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    bridge_healthy = len(traces) == len(rows) and all(
        trace["caller_input_preservation_pass"] and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"] and trace["external_call_success"]
        and trace["response_schema_valid"] and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success" and trace["validator_executed"]
        for trace in traces
    )
    prohibited = (
        "supported_adjacent_field_expansion", "supported_unsupported_caveat_expansion",
        "supported_required_fact_omission", "subject_provenance_mismatch",
    )
    clean = len(candidates) == len(rows) and all(candidate.get("validation_status") == "pass" for candidate in candidates) and not any(item in findings for item in prohibited)
    return {
        "stage": "P49-2H-4D-E2A Supported Answer Neighbor Smoke",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "comparison_pool_before": len(current_pool),
        "requested": len(rows),
        "requested_requirements": [row["canonical_requirement"] for row in rows],
        "target_only_completeness_binding_leak": False,
        "bridge_schema_hydration_validator_normal": bridge_healthy,
        "semantic_evidence_outcome_pass": sum(candidate.get("validation_status") == "pass" for candidate in candidates),
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "neighbor_smoke_go": bridge_healthy and clean and not new_failure_classes and collisions == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for exactly three E2A neighbors.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; E2A neighbor build/preflight makes zero HCX calls")
    rows = bridge.read_jsonl(args.manifest)
    validate_manifest(rows)
    current_pool, _ = register_builder.current_quality_pool()
    preflight_report = builder.preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    if not preflight_report["live_execution_allowed"] or preflight_report["comparison_pool_pass"] != 435:
        parser.error("E2A neighbor preflight failed or comparison pool is not fixed at 435; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live E2A neighbor artifact already exists; choose a new path: {path}")
    generator = bridge.configured_generator()
    corpus = {item["chunk_id"]: item for item in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [item["question"] for item in bridge.read_jsonl(bridge.FROZEN_SEED)]
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    comparison_questions = [item["question"] for item in current_pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row, adapted, mode="supported-answer-neighbor-smoke", generator=generator, corpus=corpus,
            seed_questions=seed_questions, comparison_questions=comparison_questions, max_generation_attempts=1,
        )
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])
    report = audit(rows, traces, candidates, current_pool)
    write_new_json(args.audit_output, report)
    print(json.dumps({
        key: report[key]
        for key in ("external_hcx_calls", "requested", "semantic_evidence_outcome_pass", "neighbor_smoke_go")
    } | {"audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
