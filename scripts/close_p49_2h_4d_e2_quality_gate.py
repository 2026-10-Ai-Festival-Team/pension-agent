"""Close the E2 16-record quality gate using the approved E2A replacement.

This is a local-only audit.  It replaces only the E2 IRP ETF record that was
generation_exhausted with the same-contract E2A answer-completeness pass.  It
does not promote any candidate or change the fixed 435-PASS comparison pool.
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
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts import run_p49_2h_4d_e_register_tranche as register_runner


E2_TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_trace_v3.jsonl"
E2_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_candidates_v3.jsonl"
E2A_TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_trace_v1.jsonl"
E2A_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_candidates_v1.jsonl"
NEIGHBOR_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_audit_v1.json"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_quality_gate_closure_v1.json"
TARGET_E2_ID = "P49-2H-4D-E2-HOST-0007"
TARGET_E2A_ID = "P49-2H-4D-E2A-ETF-0001"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2 quality-gate closure: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _single(rows: list[dict[str, Any]], request_id: str, label: str) -> dict[str, Any]:
    matches = [row for row in rows if row.get("remediation_request_id") == request_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {label} record for {request_id}; found {len(matches)}")
    return matches[0]


def _bridge_healthy(trace: dict[str, Any]) -> bool:
    return bool(
        trace["caller_input_preservation_pass"]
        and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"]
        and trace["external_call_success"]
        and trace["response_schema_valid"]
        and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success"
        and trace["validator_executed"]
    )


def report(
    e2_traces: list[dict[str, Any]],
    e2_candidates: list[dict[str, Any]],
    e2a_trace: dict[str, Any],
    e2a_candidate: dict[str, Any],
    neighbor_audit: dict[str, Any],
    current_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    e2_target = _single(e2_candidates, TARGET_E2_ID, "E2 target candidate")
    if e2_target.get("generation_status") != "generation_exhausted":
        raise ValueError("E2 closure may only replace the original exhausted target")
    if e2a_candidate.get("validation_status") != "pass":
        raise ValueError("E2A replacement must be a validated pass")
    identity_fields = ("coverage_cell", "target_outcome", "outcome", "question", "direct_evidence", "host_question_contract")
    mismatches = [field for field in identity_fields if e2_target.get(field) != e2a_candidate.get(field)]
    if mismatches:
        raise ValueError("E2A replacement changed host-owned identity: " + ", ".join(mismatches))

    e2_non_target_candidates = [row for row in e2_candidates if row["remediation_request_id"] != TARGET_E2_ID]
    e2_non_target_traces = [row for row in e2_traces if row["remediation_request_id"] != TARGET_E2_ID]
    if len(e2_non_target_candidates) != 15 or len(e2_non_target_traces) != 15:
        raise ValueError("E2 closure requires the 15 non-target E2 records")
    if any(row.get("validation_status") != "pass" for row in e2_non_target_candidates):
        raise ValueError("E2 non-target records must already be validated passes")

    logical_candidates = [*e2_non_target_candidates, e2a_candidate]
    logical_traces = [*e2_non_target_traces, e2a_trace]
    findings = Counter(finding for trace in logical_traces for finding in trace.get("validation_findings", []))
    finding_classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(finding_classes - bulk.KNOWN_FAILURE_CLASSES)
    metrics = register_runner.finding_metrics(logical_traces)
    dedup = bridge.full_set_dedup_audit(current_pool, logical_candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    renderer_integrity = all(
        candidate.get("question_renderer", {}).get("authority") == "host_owned"
        and isinstance(candidate.get("model_question_raw"), str)
        for candidate in logical_candidates
    )
    bridge_healthy = all(_bridge_healthy(trace) for trace in logical_traces)
    all_pass = len(logical_candidates) == 16 and all(candidate.get("validation_status") == "pass" for candidate in logical_candidates)
    strict_clean = metrics == {
        "semantic_drift": 0,
        "omission": 0,
        "near_duplicate": 0,
        "subject_loss": 0,
        "register_surface_drift": 0,
    }
    quality_go = (
        all_pass and bridge_healthy and renderer_integrity and strict_clean
        and not new_failure_classes and collisions == 0 and neighbor_audit.get("neighbor_smoke_go") is True
    )
    return {
        "stage": "P49-2H-4D-E2 Full Quality Gate Closure via E2A Replacement",
        "external_hcx_calls": 0,
        "comparison_pool_before": len(current_pool),
        "logical_e2_candidate_count": len(logical_candidates),
        "logical_e2_candidate_pass": sum(candidate.get("validation_status") == "pass" for candidate in logical_candidates),
        "e2_target_replacement": {
            "original_e2_request_id": TARGET_E2_ID,
            "replacement_e2a_request_id": TARGET_E2A_ID,
            "host_owned_identity_preserved": not mismatches,
            "replaced_generation_status": e2_target.get("generation_status"),
            "replacement_validation_status": e2a_candidate.get("validation_status"),
        },
        "bridge_schema_hydration_validator_16_of_16": bridge_healthy,
        "candidate_question_authority": "host_owned_renderer",
        "renderer_integrity": renderer_integrity,
        "aggregate_binding_and_quality_metrics": metrics,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "neighbor_smoke_go": neighbor_audit.get("neighbor_smoke_go"),
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collisions == 0,
        "e2_full_quality_gate_go": quality_go,
        "register_taxonomy_quality_gate_go": quality_go,
        "promotion_eligible_pass_count": len(logical_candidates) if quality_go else 0,
        "promotion_executed": False,
        "comparison_pool_after": len(current_pool),
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e2-trace", type=Path, default=E2_TRACE)
    parser.add_argument("--e2-candidates", type=Path, default=E2_CANDIDATES)
    parser.add_argument("--e2a-trace", type=Path, default=E2A_TRACE)
    parser.add_argument("--e2a-candidates", type=Path, default=E2A_CANDIDATES)
    parser.add_argument("--neighbor-audit", type=Path, default=NEIGHBOR_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    current_pool, _ = register_builder.current_quality_pool()
    result = report(
        read_jsonl(args.e2_trace),
        read_jsonl(args.e2_candidates),
        _single(read_jsonl(args.e2a_trace), TARGET_E2A_ID, "E2A trace"),
        _single(read_jsonl(args.e2a_candidates), TARGET_E2A_ID, "E2A candidate"),
        json.loads(args.neighbor_audit.read_text(encoding="utf-8")),
        current_pool,
    )
    write_new(args.output, result)
    print(json.dumps({
        "external_hcx_calls": 0,
        "logical_e2_candidate_pass": result["logical_e2_candidate_pass"],
        "e2_full_quality_gate_go": result["e2_full_quality_gate_go"],
        "promotion_eligible_pass_count": result["promotion_eligible_pass_count"],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
