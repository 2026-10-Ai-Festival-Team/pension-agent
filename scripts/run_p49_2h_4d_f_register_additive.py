"""Execute the exact 50-row P49-2H-4D-F host-rendered register tranche."""
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

from scripts import build_p49_2h_4d_f_register_additive as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts.p49_2h_4d_f_host_renderer import RENDERER_ID
from scripts.p49_2h_register_taxonomy import CANONICAL_REGISTERS


DEFAULT_MANIFEST = builder.DEFAULT_OUTPUT
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_audit_v1.json"


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite F register-additive artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(rows: list[dict[str, Any]]) -> None:
    expected_registers = Counter({"formal": 15, "polite": 15, "conversational": 10, "casual_banmal": 5, "terse_banmal": 5})
    if len(rows) != builder.TRANCHE_SIZE:
        raise ValueError(f"F register tranche must contain {builder.TRANCHE_SIZE} rows")
    if Counter(row.get("target_outcome") for row in rows) != Counter(builder.LANE_TARGETS):
        raise ValueError("F register tranche lane allocation drifted")
    if Counter(row.get("register") for row in rows) != expected_registers:
        raise ValueError("F register tranche canonical style allocation drifted")
    if any(row.get("register") not in CANONICAL_REGISTERS or row.get("noise_style") != "none" for row in rows):
        raise ValueError("F register tranche requires canonical registers and noise_style=none")
    if len({row.get("remediation_request_id") for row in rows}) != len(rows):
        raise ValueError("F register tranche request IDs must be unique")
    if len({row.get("register_source_manifest_request_id") for row in rows}) != len(rows):
        raise ValueError("F register tranche source request IDs must be unique")
    for row in rows:
        if row["target_outcome"] in {"supported_answer", "clarification_required"}:
            if row.get("host_question_renderer", {}).get("renderer_id") != RENDERER_ID:
                raise ValueError("supported/clarification rows must use the frozen F host renderer")
        elif row.get("host_question_renderer") is not None:
            raise ValueError("bounded rows must keep the existing bounded host renderer only")


def finding_metrics(traces: list[dict[str, Any]]) -> dict[str, int]:
    findings = [finding for trace in traces for finding in trace.get("validation_findings", [])]
    return {
        "register_subject_loss": findings.count("register_subject_loss"),
        "register_surface_drift": findings.count("register_surface_drift"),
        "semantic_drift": sum(
            finding.startswith("semantic_")
            or finding in {"bounded_temporal_drift", "bounded_target_type_drift", "bounded_concreteness_drift"}
            for finding in findings
        ),
        "required_fact_omission": findings.count("supported_required_fact_omission"),
        "clarification_missing_condition_drift": findings.count("clarification_missing_condition_drift"),
        "near_duplicate": sum(finding.startswith("near_duplicate") for finding in findings),
        "omission": sum("omission" in finding for finding in findings),
    }


def register_metrics(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    traces_by_id = {row["remediation_request_id"]: row for row in traces}
    candidates_by_id = {row["remediation_request_id"]: row for row in candidates}
    report: dict[str, dict[str, Any]] = {}
    for register in CANONICAL_REGISTERS:
        ids = [row["remediation_request_id"] for row in selected if row["register"] == register]
        scoped_traces = [traces_by_id[value] for value in ids]
        scoped_candidates = [candidates_by_id[value] for value in ids if value in candidates_by_id]
        report[register] = {
            "requested": len(ids),
            "external_calls": sum(trace["attempt_count"] for trace in scoped_traces),
            "generated": sum(trace["external_call_success"] for trace in scoped_traces),
            "pass": sum(candidate.get("validation_status") == "pass" for candidate in scoped_candidates),
            "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in scoped_traces),
            **finding_metrics(scoped_traces),
        }
    return report


def bridge_healthy(trace: dict[str, Any]) -> bool:
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


def audit(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    pass_candidates = [row for row in candidates if row.get("validation_status") == "pass"]
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - bulk.KNOWN_FAILURE_CLASSES)
    dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    metrics = finding_metrics(traces)
    clean_metrics = all(value == 0 for value in metrics.values())
    all_bridge_healthy = len(traces) == len(selected) and all(bridge_healthy(trace) for trace in traces)
    by_register = register_metrics(selected, traces, candidates)
    return {
        "stage": "P49-2H-4D-F Register Taxonomy Additive Tranche",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "comparison_pool_before": len(pool),
        "requested": len(selected),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in selected)),
        "requested_by_register": dict(Counter(row["register"] for row in selected)),
        "banmal_share": sum(row["register"] in {"casual_banmal", "terse_banmal"} for row in selected) / len(selected),
        "host_renderer_by_lane": {
            "supported_answer": RENDERER_ID,
            "clarification_required": RENDERER_ID,
            "bounded_answer": "existing_bounded_host_renderer",
        },
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(pass_candidates),
        "bridge_healthy": all_bridge_healthy,
        "register_metrics": by_register,
        "quality_metrics": metrics,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "promotion_eligible_pass_count": len(pass_candidates),
        "comparison_pool_if_promoted": len(pool) + len(pass_candidates),
        "register_additive_quality_go": (
            all_bridge_healthy and clean_metrics and not new_failure_classes and collision_count == 0
        ),
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to make exactly one HCX attempt per approved F request.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; build/preflight is the zero-HCX path")
    selected = bridge.read_jsonl(args.manifest)
    validate_manifest(selected)
    pool = builder.current_quality_pool()
    preflight = builder.preflight(selected, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    if not preflight["live_execution_allowed"] or preflight["comparison_pool_pass"] != 451:
        parser.error("F register preflight failed or comparison pool is not exactly 451; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"F register live artifact already exists; choose a new path: {path}")

    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    comparison_questions = [row["question"] for row in pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in selected:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row,
            adapted,
            mode="register-additive-tranche",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=1,
        )
        trace["register_additive_register"] = row["register"]
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidate["register_additive_register"] = row["register"]
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])
    report = audit(selected, traces, candidates, pool)
    write_new(args.audit_output, report)
    print(json.dumps({
        key: report[key]
        for key in (
            "external_hcx_calls", "comparison_pool_before", "requested", "generated_records",
            "semantic_evidence_outcome_pass", "generation_exhausted", "bridge_healthy",
            "register_additive_quality_go",
        )
    } | {"quality_metrics": report["quality_metrics"], "audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
