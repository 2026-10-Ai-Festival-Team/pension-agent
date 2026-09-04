"""One-record operational retry for the exhausted F register-tranche slot.

This script does not alter prompt, validator, source data, or the original F
trace.  It creates a fresh request ID and proves the same host-owned question
and contract remain clean against the 451 pool plus the 49 F PASS candidates.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_f_register_additive as f_builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_f_register_additive as f_runner
from scripts import run_p49_2h_4d_bulk_remediation as bulk


SOURCE_REQUEST_ID = "P49-2H-4D-F-REG-0022"
RETRY_REQUEST_ID = "P49-2H-4D-F1A-REG-0022"
DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_manifest_v1.jsonl"
DEFAULT_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_preflight_v1.json"
DEFAULT_TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_trace_v1.jsonl"
DEFAULT_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_candidates_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_audit_v1.json"


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite F1A retry artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_row(manifest_rows: list[dict[str, Any]], trace_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = next((row for row in manifest_rows if row["remediation_request_id"] == SOURCE_REQUEST_ID), None)
    trace = next((row for row in trace_rows if row["remediation_request_id"] == SOURCE_REQUEST_ID), None)
    if source is None or trace is None:
        raise ValueError("F1A source record or trace is missing")
    if trace.get("generation_status") != "generation_exhausted" or trace.get("external_call_success"):
        raise ValueError("F1A only retries the operationally exhausted F source")
    row = deepcopy(source)
    row["remediation_request_id"] = RETRY_REQUEST_ID
    row["f1a_retry_of_request_id"] = SOURCE_REQUEST_ID
    row["f1a_retry_reason"] = "generation_exhausted_without_schema_or_validator_result"
    row["register_additive_status"] = "planned_one_operational_retry"
    return row


def comparison_pool() -> list[dict[str, Any]]:
    pool = f_builder.current_quality_pool()
    f_candidates = bridge.read_jsonl(f_runner.DEFAULT_CANDIDATE_OUTPUT)
    f_pass = [row for row in f_candidates if row.get("validation_status") == "pass"]
    if len(pool) != 451 or len(f_pass) != 49:
        raise ValueError(f"F1A requires 451 + 49 comparison pool; found {len(pool)} + {len(f_pass)}")
    return [*pool, *f_pass]


def preflight(row: dict[str, Any], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    adapted, question, semantic = f_builder.rendered_question(row, semantic_rows)
    caller = bridge.caller_input_for(adapted, [candidate["question"] for candidate in pool])
    findings = (
        bridge.preservation_findings(row, adapted)
        + bridge.diversity_prompt_findings(row, caller)
        + bridge.field_boundary_prompt_findings(row, adapted, caller)
        + semantic
    )
    synthetic = [{"remediation_request_id": row["remediation_request_id"], "validation_status": "pass", "question": question}]
    dedup = bridge.full_set_dedup_audit(pool, synthetic, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    return {
        "stage": "P49-2H-4D-F1A Register Additive Operational Retry Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(pool),
        "retry_of_request_id": SOURCE_REQUEST_ID,
        "retry_request_id": row["remediation_request_id"],
        "same_host_question": question,
        "preservation_renderer_semantic_pass": not findings,
        "findings": findings,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "live_execution_allowed": not findings and collisions == 0 and len(pool) == 500,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def audit(row: dict[str, Any], trace: dict[str, Any], candidate: dict[str, Any] | None, pool: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [] if candidate is None else [candidate]
    dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    findings = trace.get("validation_findings", [])
    new_classes = sorted({bulk.failure_class(finding) for finding in findings} - bulk.KNOWN_FAILURE_CLASSES)
    healthy = f_runner.bridge_healthy(trace)
    metrics = f_runner.finding_metrics([trace])
    return {
        "stage": "P49-2H-4D-F1A Register Additive Operational Retry",
        "external_hcx_calls": trace["attempt_count"],
        "retry_of_request_id": SOURCE_REQUEST_ID,
        "retry_request_id": row["remediation_request_id"],
        "generation_status": trace["generation_status"],
        "bridge_schema_hydration_validator_normal": healthy,
        "validation_status": trace["validation_status"],
        "validation_findings": findings,
        "quality_metrics": metrics,
        "new_failure_classes": new_classes,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "retry_go": healthy and candidate is not None and candidate.get("validation_status") == "pass" and not any(metrics.values()) and not new_classes and collisions == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to make the one F1A HCX retry.")
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; F1A preflight is otherwise local-only")
    row = build_row(bridge.read_jsonl(f_runner.DEFAULT_MANIFEST), bridge.read_jsonl(f_runner.DEFAULT_TRACE_OUTPUT))
    pool = comparison_pool()
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    preflight_report = preflight(row, semantic_rows, pool)
    if not preflight_report["live_execution_allowed"]:
        parser.error("F1A preflight failed; no HCX call was made")
    for path in (args.manifest_output, args.preflight_output, args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"F1A artifact already exists; choose a new path: {path}")
    write_new(args.manifest_output, json.dumps(row, ensure_ascii=False) + "\n")
    write_new(args.preflight_output, json.dumps(preflight_report, ensure_ascii=False, indent=2) + "\n")
    generator = bridge.configured_generator()
    corpus = {item["chunk_id"]: item for item in bridge.read_jsonl(bridge.CORPUS)}
    adapted = bridge.adapt_remediation_record(row, semantic_rows)
    trace, candidate = bridge.execute_adapted_request(
        row,
        adapted,
        mode="register-additive-tranche",
        generator=generator,
        corpus=corpus,
        seed_questions=[item["question"] for item in bridge.read_jsonl(bridge.FROZEN_SEED)],
        comparison_questions=[item["question"] for item in pool],
        max_generation_attempts=1,
    )
    bridge.append_jsonl(args.trace_output, [trace])
    if candidate is not None:
        bridge.append_jsonl(args.candidate_output, [candidate])
    report = audit(row, trace, candidate, pool)
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": report["external_hcx_calls"],
        "generation_status": report["generation_status"],
        "validation_status": report["validation_status"],
        "retry_go": report["retry_go"],
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
