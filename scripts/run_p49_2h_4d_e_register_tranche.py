"""Execute the preflighted 20-record P49-2H-4D-E register tranche.

The runner consumes the fixed 435-PASS pool from the D-D anchor promotion and
reports casual_banmal and terse_banmal independently.  It is not a bulk path:
exactly the immutable 20-row additive manifest is accepted, and no acceptance,
export, or tuning state is changed.
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

from scripts import build_p49_2h_4d_e_register_tranche as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS


DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_manifest_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_audit_v1.json"


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite register-tranche artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 20:
        raise ValueError(f"register tranche must have exactly 20 rows; found {len(rows)}")
    styles = Counter(row.get("register") for row in rows)
    if styles != Counter({"casual_banmal": 10, "terse_banmal": 10}):
        raise ValueError(f"unexpected register tranche style allocation: {dict(styles)}")
    if any(row.get("noise_style") != "none" for row in rows):
        raise ValueError("register tranche must keep noise_style=none")
    if len({row.get("remediation_request_id") for row in rows}) != 20:
        raise ValueError("register tranche request IDs must be unique")


def finding_metrics(traces: list[dict[str, Any]]) -> dict[str, int]:
    findings = [finding for trace in traces for finding in trace.get("validation_findings", [])]
    return {
        # Register-surface drift is intentionally reported separately from a
        # semantic contract drift.  The first live audit exposed that an
        # aggregate suffix match would otherwise double-count it.
        "semantic_drift": sum(
            finding.startswith("semantic_")
            or (finding.endswith("_drift") and not finding.startswith("register_"))
            for finding in findings
        ),
        "omission": sum("omission" in finding for finding in findings),
        "near_duplicate": sum(finding.startswith("near_duplicate") for finding in findings),
        "subject_loss": findings.count("register_subject_loss"),
        "register_surface_drift": findings.count("register_surface_drift"),
    }


def style_audit(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    trace_by_id = {row["remediation_request_id"]: row for row in traces}
    candidate_by_id = {row["remediation_request_id"]: row for row in candidates}
    report: dict[str, Any] = {}
    for style in sorted(BANMAL_REGISTERS):
        ids = [row["remediation_request_id"] for row in selected if row["register"] == style]
        style_traces = [trace_by_id[request_id] for request_id in ids]
        style_candidates = [candidate_by_id[request_id] for request_id in ids if request_id in candidate_by_id]
        report[style] = {
            "requested": len(ids),
            "external_calls": sum(trace["attempt_count"] for trace in style_traces),
            "generated": sum(trace["external_call_success"] for trace in style_traces),
            "pass": sum(candidate.get("validation_status") == "pass" for candidate in style_candidates),
            "exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in style_traces),
            "candidate_bridge_failed": sum(trace["generation_status"] == "candidate_bridge_failed" for trace in style_traces),
            **finding_metrics(style_traces),
        }
    return report


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
    styles = style_audit(selected, traces, candidates)
    styles_clean = all(
        metrics["pass"] > 0
        and not metrics["subject_loss"]
        and not metrics["register_surface_drift"]
        for metrics in styles.values()
    )
    return {
        "stage": "P49-2H-4D-E Register Taxonomy Tranche",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "comparison_pool_before": len(current_pool),
        "requested": len(selected),
        "requested_by_register": dict(Counter(row["register"] for row in selected)),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in selected)),
        "noise_style_counts": dict(Counter(row["noise_style"] for row in selected)),
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(pass_candidates),
        "bridge_healthy": bridge_healthy,
        "style_metrics": styles,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "promotion_eligible_pass_count": len(pass_candidates),
        "comparison_pool_if_promoted": len(current_pool) + len(pass_candidates),
        "register_taxonomy_go": bridge_healthy and styles_clean and not new_failure_classes and collision_count == 0,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for the exact 20-record register tranche.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    parser.add_argument("--audit-existing", action="store_true", help="Local-only: recompute an existing tranche audit without HCX calls.")
    parser.add_argument("--existing-trace", type=Path, help="Trace JSONL required by --audit-existing.")
    parser.add_argument("--existing-candidates", type=Path, help="Candidate JSONL required by --audit-existing.")
    args = parser.parse_args()
    if args.audit_existing:
        if args.live or not args.existing_trace or not args.existing_candidates:
            parser.error("--audit-existing is local-only and requires --existing-trace plus --existing-candidates")
    elif not args.live:
        parser.error("--live is required; the zero-HCX build/preflight is a separate immutable artifact")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")
    selected = bridge.read_jsonl(args.manifest)
    validate_manifest(selected)
    current_pool, _ = builder.current_quality_pool()
    preflight_report = builder.preflight(selected, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    if not preflight_report["live_execution_allowed"] or preflight_report["comparison_pool_pass"] != 435:
        parser.error("register-tranche preflight failed or comparison pool is not fixed at 435; no HCX call was made")
    if args.audit_existing:
        traces = bridge.read_jsonl(args.existing_trace)
        candidates = bridge.read_jsonl(args.existing_candidates)
        expected_ids = {row["remediation_request_id"] for row in selected}
        if {row.get("remediation_request_id") for row in traces} != expected_ids:
            parser.error("existing trace does not match the fixed 20-row register tranche")
        report = audit(selected, traces, candidates, current_pool)
        write_new_json(args.audit_output, report)
        print(json.dumps({
            "external_hcx_calls": 0,
            "requested": report["requested"],
            "semantic_evidence_outcome_pass": report["semantic_evidence_outcome_pass"],
            "register_taxonomy_go": report["register_taxonomy_go"],
            "audit_output": str(args.audit_output),
        }, ensure_ascii=False))
        return
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live register-tranche artifact already exists; choose a new path: {path}")

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
            mode="register-tranche",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["register_tranche_style"] = row["register"]
        trace["noise_style"] = row["noise_style"]
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidate["register_tranche_style"] = row["register"]
            candidate["noise_style"] = row["noise_style"]
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
            "bridge_healthy",
            "register_taxonomy_go",
        )
    } | {"style_metrics": report["style_metrics"], "audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
