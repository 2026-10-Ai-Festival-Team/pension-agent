"""Execute only the 16-record live tranche from preflighted P49-2H-4D-E2."""
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
from scripts import build_p49_2h_4d_e2_host_renderer as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts import run_p49_2h_4d_e_register_tranche as register_runner


DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_manifest_v1.jsonl"
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_audit_v1.json"


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2 renderer artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_live(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("e2_execution_tier") == "live"]
    if len(selected) != 16 or Counter((row["target_outcome"], row["register"]) for row in selected) != builder.LIVE_ALLOCATION:
        raise ValueError("E2 must select exactly 16 live rows: 4 per lane/register")
    if any(row.get("host_question_renderer", {}).get("renderer_id") != builder.RENDERER_ID for row in selected):
        raise ValueError("E2 live row lacks the approved host question renderer")
    if any(row.get("noise_style") != "none" for row in selected):
        raise ValueError("E2 live row must keep noise_style=none")
    return selected


def audit(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    pass_candidates = [row for row in candidates if row.get("validation_status") == "pass"]
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    classes = {bulk.failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - bulk.KNOWN_FAILURE_CLASSES)
    dedup = bridge.full_set_dedup_audit(current_pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
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
    metrics = register_runner.finding_metrics(traces)
    renderer_integrity = all(
        candidate.get("question_renderer", {}).get("authority") == "host_owned"
        and isinstance(candidate.get("model_question_raw"), str)
        for candidate in candidates
    )
    strict_clean = (
        len(pass_candidates) == len(selected)
        and not any(trace["generation_status"] == "generation_exhausted" for trace in traces)
        and metrics == {
            "semantic_drift": 0,
            "omission": 0,
            "near_duplicate": 0,
            "subject_loss": 0,
            "register_surface_drift": 0,
        }
    )
    e2_go = bridge_healthy and renderer_integrity and strict_clean and not new_failure_classes and collision_count == 0
    return {
        "stage": "P49-2H-4D-E2 Host-Owned Banmal Surface Renderer Live Tranche",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "comparison_pool_before": len(current_pool),
        "requested": len(selected),
        "requested_by_lane_and_register": {
            f"{lane}:{register}": count
            for (lane, register), count in sorted(Counter((row["target_outcome"], row["register"]) for row in selected).items())
        },
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(pass_candidates),
        "bridge_schema_hydration_validator_16_of_16": bridge_healthy,
        "candidate_question_authority": "host_owned_renderer",
        "hcx_model_question_authority": "audit_only",
        "renderer_integrity": renderer_integrity,
        "aggregate_binding_and_quality_metrics": metrics,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": new_failure_classes,
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "initial_e_candidate_promotion_held": True,
        "e1_candidate_promotion_held": True,
        "e2_candidate_promotion_held": True,
        "register_taxonomy_e2_go": e2_go,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to call HCX for the exact E2 16-record live tranche.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; E2 build/preflight makes zero HCX calls")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")
    rows = bridge.read_jsonl(args.manifest)
    selected = select_live(rows)
    current_pool, _ = register_builder.current_quality_pool()
    preflight_report = builder.preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    if not preflight_report["live_execution_allowed"] or preflight_report["comparison_pool_pass"] != 435:
        parser.error("E2 renderer preflight failed or comparison pool is not fixed at 435; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live E2 artifact already exists; choose a new path: {path}")

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
            row, adapted, mode="host-renderer-tranche", generator=generator,
            corpus=corpus, seed_questions=seed_questions, comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["candidate_question_authority"] = "host_owned_renderer"
        trace["hcx_model_question_authority"] = "audit_only"
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
            "external_hcx_calls", "comparison_pool_before", "requested", "semantic_evidence_outcome_pass",
            "generation_exhausted", "bridge_schema_hydration_validator_16_of_16", "renderer_integrity",
            "register_taxonomy_e2_go",
        )
    } | {"audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
