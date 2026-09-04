"""P49-2H-4D: guarded 75–100 record deficit-remediation batches.

This orchestrator deliberately reuses the tested P49-2H-4C adapter, HCX
caller, canonical v4 candidate bridge, hydration, and validator.  It does not
alter the 4B manifest, prompt contract, validator, or dedup threshold.  A
batch always compares against the complete existing PASS pool and writes a
local-only cumulative dedup report before any later batch can be considered.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge


MANIFEST = bridge.REMEDIATION_MANIFEST
SEMANTIC_REQUESTS = bridge.SEMANTIC_REQUESTS
COMPARISON_POOL = bridge.COMPARISON_POOL
DEFAULT_BASELINE_CANDIDATES = (
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_smoke_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_retry_candidates_v1.jsonl",
)
DEFAULT_TRACE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_trace_v1.jsonl"
DEFAULT_CANDIDATE_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_candidates_v1.jsonl"
DEFAULT_AUDIT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_cumulative_audit_v1.json"
DEFAULT_PREFLIGHT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_preflight_v1.json"

BATCH_MIN = 75
BATCH_MAX = 100
TARGET_TOTAL = 600
LANE_ORDER = ("supported_answer", "clarification_required", "bounded_answer")
BOUNDED_EXHAUSTION_CLASSES = (
    "near_duplicate",
    "semantic_subject",
    "subject_provenance",
    "target_drift",
    "other_existing_class",
    "no_validator_finding",
)

# This is the fixed failure-class vocabulary observed in the frozen 3F
# validation results plus the existing generic frozen-seed dedup route.
# ``semantic_forbidden_field_expansion`` is a regression-covered defensive
# class: it remains a validator failure, but its 5A fix is independently
# attributed and verified rather than being misreported as a newly discovered
# class in later batch audits. Any other class is surfaced in the report and
# blocks advancement to another batch; nothing here weakens or waives the
# validator.
KNOWN_FAILURE_CLASSES = frozenset(
    {
        "near_duplicate_candidate",
        "near_duplicate_frozen_seed",
        "semantic_subject_mismatch",
        "supported_question_scope_drift",
        "subject_provenance_mismatch",
        "supported_required_fact_omission",
        "clarification_missing_condition_drift",
        "semantic_forbidden_field_expansion",
        "register_subject_loss",
        "register_surface_drift",
    }
)


def read_many(paths: list[Path] | tuple[Path, ...]) -> list[dict[str, Any]]:
    return [row for path in paths for row in bridge.read_jsonl(path)]


def distinct_pass_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one PASS candidate per remediation ID and reject conflicts.

    An exhausted candidate is never promoted.  Therefore, a later PASS for
    the same remediation ID is the canonical replacement for that unresolved
    earlier attempt; two promoted PASS rows for one ID are still refused.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("validation_status") != "pass":
            continue
        request_id = row.get("remediation_request_id")
        if not request_id:
            continue
        if request_id in by_id:
            raise ValueError(f"multiple PASS candidates for remediation request: {request_id}")
        by_id[request_id] = row
    return list(by_id.values())


def proportional_quotas(remaining_by_lane: dict[str, list[dict[str, Any]]], batch_size: int) -> dict[str, int]:
    """Allocate a deterministic balanced batch without changing manifest rows."""
    total = sum(len(rows) for rows in remaining_by_lane.values())
    if total < batch_size:
        raise ValueError(f"only {total} unresolved remediation rows remain; cannot select a {batch_size}-record batch")
    raw = {lane: len(remaining_by_lane[lane]) * batch_size / total for lane in LANE_ORDER}
    quotas = {lane: int(raw[lane]) for lane in LANE_ORDER}
    for lane in sorted(LANE_ORDER, key=lambda item: (raw[item] - quotas[item], -LANE_ORDER.index(item)), reverse=True)[: batch_size - sum(quotas.values())]:
        quotas[lane] += 1
    if any(quotas[lane] > len(remaining_by_lane[lane]) for lane in LANE_ORDER):
        raise AssertionError("proportional quota exceeds unresolved lane capacity")
    return quotas


def select_balanced_batch(rows: list[dict[str, Any]], completed_ids: set[str], batch_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Select earliest unresolved rows within a proportional three-lane batch."""
    remaining_by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["remediation_request_id"] not in completed_ids:
            remaining_by_lane[row["target_outcome"]].append(row)
    if set(remaining_by_lane) != set(LANE_ORDER):
        raise ValueError("unresolved 4B remediation rows must include all three outcome lanes")
    quotas = proportional_quotas(remaining_by_lane, batch_size)
    selected_ids = {
        row["remediation_request_id"]
        for lane in LANE_ORDER
        for row in remaining_by_lane[lane][: quotas[lane]]
    }
    selected = [row for row in rows if row["remediation_request_id"] in selected_ids]
    if len(selected) != batch_size:
        raise AssertionError("balanced batch selection lost or duplicated a manifest row")
    return selected, quotas


def failure_class(finding: str) -> str:
    return finding.split(":", 1)[0]


def bounded_exhaustion_class(finding: str) -> str:
    """Normalize existing validator findings for bounded-lane operational audit."""
    kind = failure_class(finding)
    if kind.startswith("near_duplicate"):
        return "near_duplicate"
    if kind == "semantic_subject_mismatch":
        return "semantic_subject"
    if kind == "subject_provenance_mismatch":
        return "subject_provenance"
    if kind.endswith("_drift"):
        return "target_drift"
    return "other_existing_class"


def bounded_cell_audit(
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    pass_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Report bounded generation outcomes by immutable coverage cell.

    A candidate is either promoted PASS or remains generation_exhausted after
    the existing retry contract. Failure breakdown counts final validator
    findings, so a row with more than one finding is intentionally visible in
    every relevant existing-class bucket.
    """
    trace_by_id = {trace["remediation_request_id"]: trace for trace in traces}
    pass_ids = {row["remediation_request_id"] for row in pass_candidates}
    by_cell: dict[str, dict[str, Any]] = {}
    for row in selected:
        if row["target_outcome"] != "bounded_answer":
            continue
        cell = row["coverage_cell"]
        entry = by_cell.setdefault(
            cell,
            {
                "coverage_cell": cell,
                "requested": 0,
                "pass": 0,
                "exhausted": 0,
                "exhaustion_failure_class_breakdown": {kind: 0 for kind in BOUNDED_EXHAUSTION_CLASSES},
            },
        )
        entry["requested"] += 1
        request_id = row["remediation_request_id"]
        if request_id in pass_ids:
            entry["pass"] += 1
            continue
        trace = trace_by_id[request_id]
        if trace["generation_status"] != "generation_exhausted":
            continue
        entry["exhausted"] += 1
        findings = trace.get("validation_findings", [])
        if not findings:
            entry["exhaustion_failure_class_breakdown"]["no_validator_finding"] += 1
        for finding in findings:
            entry["exhaustion_failure_class_breakdown"][bounded_exhaustion_class(finding)] += 1
    return [by_cell[cell] for cell in sorted(by_cell)]


def subject_provenance_repeat_audit(
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    *,
    manifest_by_id: dict[str, dict[str, Any]],
    prior_traces: list[dict[str, Any]],
) -> dict[str, Any]:
    """Distinguish a newly observed mismatch from a repeated cell/subject pair."""
    prior_mismatches = [
        trace
        for trace in prior_traces
        if "subject_provenance_mismatch" in trace.get("validation_findings", [])
    ]
    records: list[dict[str, Any]] = []
    for trace in traces:
        if "subject_provenance_mismatch" not in trace.get("validation_findings", []):
            continue
        request_id = trace["remediation_request_id"]
        row = manifest_by_id[request_id]
        same_cell_subject = []
        same_subject_requirement = []
        for prior in prior_mismatches:
            prior_row = manifest_by_id[prior["remediation_request_id"]]
            if prior_row["coverage_cell"] == row["coverage_cell"] and prior_row.get("subject") == row.get("subject"):
                same_cell_subject.append(prior["remediation_request_id"])
            if (
                prior_row.get("subject") == row.get("subject")
                and prior_row.get("canonical_requirement") == row.get("canonical_requirement")
            ):
                same_subject_requirement.append(prior["remediation_request_id"])
        records.append(
            {
                "remediation_request_id": request_id,
                "coverage_cell": row["coverage_cell"],
                "subject": row.get("subject"),
                "canonical_requirement": row.get("canonical_requirement"),
                "prior_same_cell_subject_request_ids": same_cell_subject,
                "repeated_same_cell_subject": bool(same_cell_subject),
                "prior_same_subject_requirement_request_ids": same_subject_requirement,
                "repeated_same_subject_requirement": bool(same_subject_requirement),
            }
        )
    return {
        "current_count": len(records),
        "repeated_same_cell_subject_count": sum(record["repeated_same_cell_subject"] for record in records),
        "repeated_same_subject_requirement_count": sum(record["repeated_same_subject_requirement"] for record in records),
        "records": records,
    }


def lane_yield_snapshot(observed_audits: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    requested = Counter()
    passed = Counter()
    for audit in observed_audits:
        requested.update(audit["outcome_requested"])
        passed.update(audit["outcome_pass"])
    return {
        lane: {
            "requested": requested[lane],
            "pass": passed[lane],
            "yield": round(passed[lane] / requested[lane], 6) if requested[lane] else None,
        }
        for lane in LANE_ORDER
    }


def capacity_projection(
    *,
    manifest_rows: list[dict[str, Any]],
    all_candidate_rows: list[dict[str, Any]],
    observed_audits: list[dict[str, Any]],
    reserve_buffer_paths: list[Path],
    current_cumulative_pass: int,
) -> dict[str, Any]:
    """Project original-manifest capacity plus only explicitly named reserves."""
    from scripts import build_p49_2h_4d_capacity_buffer_manifest as buffer_builder

    lane_yields = buffer_builder.lane_yields(observed_audits)
    promoted = buffer_builder.distinct_pass_by_request(all_candidate_rows)
    capacities = buffer_builder.cell_capacity(manifest_rows, promoted, lane_yields)
    unresolved_by_lane = Counter(
        row["target_outcome"]
        for row in manifest_rows
        if row["remediation_request_id"] not in promoted
    )
    expected_original_pass = sum(unresolved_by_lane[lane] * lane_yields[lane] for lane in LANE_ORDER)
    reserve_expected: dict[str, float] = {}
    reserve_counts: dict[str, dict[str, int]] = {}
    for path in reserve_buffer_paths:
        rows = bridge.read_jsonl(path)
        counts = Counter(row["target_outcome"] for row in rows)
        reserve_counts[path.stem] = {lane: counts[lane] for lane in LANE_ORDER}
        reserve_expected[path.stem] = sum(counts[lane] * lane_yields[lane] for lane in LANE_ORDER)
    reserve_total = sum(reserve_expected.values())
    projected_total = current_cumulative_pass + expected_original_pass + reserve_total
    return {
        "observed_lane_yields": lane_yields,
        "unresolved_original_by_lane": {lane: unresolved_by_lane[lane] for lane in LANE_ORDER},
        "expected_remaining_original_pass": round(expected_original_pass, 6),
        "projected_original_residual_before_reserve": round(
            sum(row["expected_residual_deficit"] for row in capacities),
            6,
        ),
        "reserve_buffer_outcome_counts": reserve_counts,
        "reserve_buffer_expected_pass": {name: round(value, 6) for name, value in reserve_expected.items()},
        "projected_total_with_reserves": round(projected_total, 6),
        "projected_cushion_with_reserves": round(projected_total - TARGET_TOTAL, 6),
    }


def preflight_batch(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Exercise adapter/preservation/prompt binding for every selected row, with zero calls."""
    failures: list[dict[str, Any]] = []
    for row in rows:
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            preservation = bridge.preservation_findings(row, adapted)
            prompt_findings = bridge.diversity_prompt_findings(row, bridge.caller_input_for(adapted, [])) if not preservation else []
            if preservation or prompt_findings:
                failures.append(
                    {
                        "remediation_request_id": row["remediation_request_id"],
                        "preservation_findings": preservation,
                        "diversity_prompt_findings": prompt_findings,
                    }
                )
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    return {
        "stage": "P49-2H-4D batch preflight",
        "external_hcx_calls": 0,
        "requested": len(rows),
        "outcome_requested": dict(Counter(row["target_outcome"] for row in rows)),
        "preservation_and_prompt_pass": len(rows) - len(failures),
        "failures": failures,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def cumulative_summary(
    *,
    batch_label: str,
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    baseline_records: list[dict[str, Any]],
    completed_before: set[str],
    total_manifest_rows: int,
    manifest_by_id: dict[str, dict[str, Any]] | None = None,
    prior_traces: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize yield and audit the exact cumulative PASS pool."""
    pass_candidates = distinct_pass_rows(candidates)
    dedup = bridge.full_set_dedup_audit(
        baseline_records,
        candidates,
        bridge.read_jsonl(bridge.FROZEN_SEED),
    )
    findings = [finding for trace in traces for finding in trace.get("validation_findings", [])]
    finding_counts = Counter(findings)
    classes = {failure_class(finding) for finding in findings}
    new_failure_classes = sorted(classes - KNOWN_FAILURE_CLASSES)
    lane_pass = Counter(candidate["outcome"] for candidate in pass_candidates)
    exhausted = [trace for trace in traces if trace["generation_status"] == "generation_exhausted"]
    lane_exhausted = Counter(
        next(row["target_outcome"] for row in selected if row["remediation_request_id"] == trace["remediation_request_id"])
        for trace in exhausted
    )
    semantic_fail = [trace for trace in exhausted if trace.get("validation_findings")]
    semantic_not_evaluated = [trace for trace in exhausted if not trace.get("validation_findings")]
    cumulative_pass = len(baseline_records) + len(pass_candidates)
    pass_ids = {candidate["remediation_request_id"] for candidate in pass_candidates}
    retryable_ids = {
        trace["remediation_request_id"]
        for trace in traces
        if trace["remediation_request_id"] not in pass_ids
    }
    unattempted_manifest_rows = total_manifest_rows - len(completed_before) - len(selected)
    # A generation-exhausted row is still an unresolved manifest deficit: it
    # can be retried with the same contract and must not be treated as an
    # irrevocably consumed slot in the 600-candidate buffer calculation.
    unresolved_manifest_slots = unattempted_manifest_rows + len(retryable_ids)
    remaining_needed = max(0, TARGET_TOTAL - cumulative_pass)
    observed_pass_rate = len(pass_candidates) / len(selected) if selected else 0.0
    best_case_final = cumulative_pass + unresolved_manifest_slots
    projected_final = cumulative_pass + observed_pass_rate * unresolved_manifest_slots
    projected_shortfall = max(0.0, TARGET_TOTAL - projected_final)
    estimated_buffer_requests = (
        math.ceil(projected_shortfall / observed_pass_rate) if observed_pass_rate > 0 else None
    )
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    return {
        "stage": "P49-2H-4D Batched Bulk Deficit Remediation",
        "batch_label": batch_label,
        "requested": len(selected),
        "outcome_requested": dict(Counter(row["target_outcome"] for row in selected)),
        "external_calls_attempted": sum(trace["attempt_count"] for trace in traces),
        "generated": sum(trace["external_call_success"] for trace in traces),
        "exhausted": len(exhausted),
        "semantic_pass": len(pass_candidates),
        "semantic_fail": len(semantic_fail),
        "semantic_not_evaluated": len(semantic_not_evaluated),
        "outcome_pass": {lane: lane_pass[lane] for lane in LANE_ORDER},
        "outcome_exhausted": {lane: lane_exhausted[lane] for lane in LANE_ORDER},
        "bounded_cell_audit": bounded_cell_audit(selected, traces, pass_candidates),
        "subject_provenance_repeat_audit": subject_provenance_repeat_audit(
            selected,
            traces,
            manifest_by_id=manifest_by_id or {row["remediation_request_id"]: row for row in selected},
            prior_traces=prior_traces or [],
        ),
        "near_duplicate": sum(count for finding, count in finding_counts.items() if finding.startswith("near_duplicate")),
        "subject_provenance_mismatch": finding_counts["subject_provenance_mismatch"],
        "failure_classes": dict(sorted(finding_counts.items())),
        "new_failure_classes": new_failure_classes,
        "caller_input_preservation_failures": [trace["remediation_request_id"] for trace in traces if not trace["caller_input_preservation_pass"]],
        "response_schema_failures": [trace["remediation_request_id"] for trace in traces if trace["response_schema_valid"] is False],
        "cumulative_dedup": dedup,
        "cumulative_pass": cumulative_pass,
        "unattempted_manifest_rows": unattempted_manifest_rows,
        "retryable_exhausted_slots": len(retryable_ids),
        "unresolved_manifest_slots": unresolved_manifest_slots,
        "remaining_needed_for_600": remaining_needed,
        "required_pass_rate_for_600_from_unresolved": round(remaining_needed / unresolved_manifest_slots, 6) if unresolved_manifest_slots else None,
        "best_case_final_without_new_manifest": best_case_final,
        "raw_buffer_at_100_percent_yield": best_case_final - TARGET_TOTAL,
        "observed_batch_pass_rate": round(observed_pass_rate, 6),
        "projected_final_at_observed_pass_rate": round(projected_final, 3),
        "projected_shortfall_at_observed_pass_rate": round(projected_shortfall, 3),
        "estimated_additional_manifest_requests_at_observed_pass_rate": estimated_buffer_requests,
        "buffer_planning_required": projected_shortfall > 0,
        "next_batch_allowed": not new_failure_classes and collision_count == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing 4D artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Required to make a single 75–100 record HCX-007 batch.")
    parser.add_argument("--batch-size", type=int, default=75, help="Inclusive 75–100 batch size; defaults to the cautious first batch of 75.")
    parser.add_argument("--batch-label", default="P49-2H-4D-BATCH-01")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--semantic-requests", type=Path, default=SEMANTIC_REQUESTS)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--baseline-candidates", type=Path, action="append", help="Existing validated 4C candidate JSONL; defaults to the two 4C-3 artifacts.")
    parser.add_argument("--prior-batch-candidates", type=Path, action="append", help="Prior 4D candidate JSONL included in cumulative dedup and completion selection.")
    parser.add_argument("--prior-batch-trace", type=Path, action="append", help="Prior 4D trace JSONL used only for subject/provenance repeat detection.")
    parser.add_argument("--prior-batch-audit", type=Path, action="append", help="Prior 4D audit JSON used for cumulative and recent-two-batch lane yield reporting.")
    parser.add_argument("--reserve-buffer", type=Path, action="append", help="Ready-but-unexecuted buffer manifest included only in capacity projection.")
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT_OUTPUT)
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT_OUTPUT)
    parser.add_argument("--audit-existing", action="store_true", help="Local-only: recompute a completed batch audit from immutable trace/candidate artifacts.")
    parser.add_argument("--existing-trace", type=Path, help="Trace JSONL required by --audit-existing.")
    parser.add_argument("--existing-candidates", type=Path, help="Candidate JSONL required by --audit-existing.")
    parser.add_argument("--expected-baseline-pass", type=int, default=145, help="Fail closed unless existing immutable plus prior PASS pool matches this count.")
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()

    if not BATCH_MIN <= args.batch_size <= BATCH_MAX:
        parser.error(f"--batch-size must be within {BATCH_MIN}..{BATCH_MAX}")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")

    manifest_rows = bridge.read_jsonl(args.manifest)
    semantic_rows = bridge.read_jsonl(args.semantic_requests)
    immutable_pass = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    baseline_paths = args.baseline_candidates or list(DEFAULT_BASELINE_CANDIDATES)
    prior_paths = args.prior_batch_candidates or []
    prior_trace_paths = args.prior_batch_trace or []
    prior_audit_paths = args.prior_batch_audit or []
    reserve_buffer_paths = args.reserve_buffer or []
    prior_pass = distinct_pass_rows(read_many([*baseline_paths, *prior_paths]))
    baseline_records = [*immutable_pass, *prior_pass]
    if len(immutable_pass) != 133 or len(baseline_records) != args.expected_baseline_pass:
        parser.error(
            f"expected immutable 133 and cumulative baseline {args.expected_baseline_pass}; got {len(immutable_pass)} and {len(baseline_records)}"
        )
    completed_before = {row["remediation_request_id"] for row in prior_pass}
    manifest_by_id = {row["remediation_request_id"]: row for row in manifest_rows}
    prior_traces = read_many(prior_trace_paths)
    prior_audits = [json.loads(path.read_text(encoding="utf-8")) for path in prior_audit_paths]
    selected, quotas = select_balanced_batch(manifest_rows, completed_before, args.batch_size)
    preflight = preflight_batch(selected, semantic_rows)
    preflight["batch_label"] = args.batch_label
    preflight["planned_lane_quotas"] = quotas

    if args.audit_existing:
        if args.live or not args.existing_trace or not args.existing_candidates:
            parser.error("--audit-existing is local-only and requires --existing-trace plus --existing-candidates")
        traces = bridge.read_jsonl(args.existing_trace)
        candidates = bridge.read_jsonl(args.existing_candidates)
        selected_ids = {row["remediation_request_id"] for row in selected}
        if {row["remediation_request_id"] for row in traces} != selected_ids:
            parser.error("existing trace does not match the deterministic selected batch")
        summary = cumulative_summary(
            batch_label=args.batch_label,
            selected=selected,
            traces=traces,
            candidates=candidates,
            baseline_records=baseline_records,
            completed_before=completed_before,
            total_manifest_rows=len(manifest_rows),
            manifest_by_id=manifest_by_id,
            prior_traces=prior_traces,
        )
        observed_audits = [*prior_audits, summary]
        summary["cumulative_lane_yield"] = lane_yield_snapshot(observed_audits)
        summary["recent_two_batch_lane_yield"] = lane_yield_snapshot(observed_audits[-2:])
        summary["capacity_projection"] = capacity_projection(
            manifest_rows=manifest_rows,
            all_candidate_rows=[*read_many([*baseline_paths, *prior_paths]), *candidates],
            observed_audits=observed_audits,
            reserve_buffer_paths=reserve_buffer_paths,
            current_cumulative_pass=summary["cumulative_pass"],
        )
        write_new_json(args.audit_output, summary)
        print(json.dumps({"batch_label": args.batch_label, "external_hcx_calls": 0, "cumulative_pass": summary["cumulative_pass"], "buffer_planning_required": summary["buffer_planning_required"], "audit_output": str(args.audit_output)}, ensure_ascii=False))
        return

    if not args.live:
        write_new_json(args.preflight_output, preflight)
        print(json.dumps({**{key: preflight[key] for key in ("batch_label", "requested", "outcome_requested", "preservation_and_prompt_pass")}, "external_hcx_calls": 0, "preflight_output": str(args.preflight_output)}, ensure_ascii=False))
        return
    if preflight["failures"]:
        parser.error("preflight preservation or diversity prompt binding failed; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"live 4D artifact already exists; choose a new path: {path}")

    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    comparison_questions = [row["question"] for row in baseline_records]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in selected:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row,
            adapted,
            mode="batch-live",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["batch_label"] = args.batch_label
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidate["batch_label"] = args.batch_label
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])

    summary = cumulative_summary(
        batch_label=args.batch_label,
        selected=selected,
        traces=traces,
        candidates=candidates,
        baseline_records=baseline_records,
        completed_before=completed_before,
        total_manifest_rows=len(manifest_rows),
        manifest_by_id=manifest_by_id,
        prior_traces=prior_traces,
    )
    observed_audits = [*prior_audits, summary]
    summary["cumulative_lane_yield"] = lane_yield_snapshot(observed_audits)
    summary["recent_two_batch_lane_yield"] = lane_yield_snapshot(observed_audits[-2:])
    summary["capacity_projection"] = capacity_projection(
        manifest_rows=manifest_rows,
        all_candidate_rows=[*read_many([*baseline_paths, *prior_paths]), *candidates],
        observed_audits=observed_audits,
        reserve_buffer_paths=reserve_buffer_paths,
        current_cumulative_pass=summary["cumulative_pass"],
    )
    write_new_json(args.audit_output, summary)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "batch_label",
                    "requested",
                    "generated",
                    "exhausted",
                    "semantic_pass",
                    "semantic_fail",
                    "new_failure_classes",
                    "cumulative_pass",
                    "unresolved_manifest_slots",
                    "raw_buffer_at_100_percent_yield",
                    "projected_shortfall_at_observed_pass_rate",
                    "next_batch_allowed",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
