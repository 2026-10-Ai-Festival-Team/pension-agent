"""Build and preflight P49-2H-4D-C's bounded targeted v6 manifest.

This is a zero-HCX planning artifact for the four bounded cells whose recent
attempts were near-duplicate constrained.  It preserves every semantic and
provenance field from an immutable 4B source row while assigning a new,
explicit host-owned wording profile.  It deliberately does not claim capacity
credit for a cell whose recent empirical yield is zero.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk


MANIFEST = bridge.REMEDIATION_MANIFEST
COMPARISON_POOL = bridge.COMPARISON_POOL
TARGET_CELLS = (
    "D12-Q12-bounded_answer",
    "D17-Q17-bounded_answer",
    "D18-Q18-bounded_answer",
    "D20-Q12-bounded_answer",
)
DEFAULT_CANDIDATES = (
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_smoke_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_retry_candidates_v1.jsonl",
    *(ROOT / f"evaluation/fine_tuning/p49_2h_4d_batch_{batch:02d}_candidates_v1.jsonl" for batch in range(1, 7)),
    ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_same_record_retest_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_neighbor_candidates_v1.jsonl",
)
DEFAULT_TRACES = (
    *(ROOT / f"evaluation/fine_tuning/p49_2h_4d_batch_{batch:02d}_trace_v1.jsonl" for batch in range(1, 7)),
    ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_same_record_retest_trace_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_neighbor_trace_v1.jsonl",
)
DEFAULT_RECENT_TRACES = (
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_05_trace_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_06_trace_v1.jsonl",
)
DEFAULT_RESERVES = (
    ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_buffer_v4.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_buffer_v5.jsonl",
)
DEFAULT_BATCH_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_06_cumulative_audit_v1.json"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_c_bounded_targeted_v6_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_c_bounded_targeted_v6_audit_v1.json"


# Every new profile uses a context frame and a speech act that did not exist in
# the frozen four-dimensional 4B design.  The 2/4/4/2 allocation is an
# exploratory tranche, not a capacity claim: zero-yield cells receive enough
# distinct profiles to measure recovery without pretending that extra rows
# alone solve their exhausted language space.
V6_PROFILES: dict[str, tuple[dict[str, str], ...]] = {
    "D12-Q12-bounded_answer": (
        {
            "user_situation_frame": "공시자료 검토 중",
            "speech_act": "자료 범위 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "향후",
            "misconception_type": "미래 값이 이미 확정됐다는 전제",
            "sentence_shape": "상황절+근거범위 확인",
            "query_form": "evidence_limit",
            "register": "general",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "연말 자금 계획 중",
            "speech_act": "계획 전제 점검",
            "information_gap_mode": "미래 수치 미확정 점검",
            "temporal_expression": "앞으로",
            "misconception_type": "향후 시점에도 같은 값이라는 전제",
            "sentence_shape": "계획절+정보공백 확인",
            "query_form": "planning_check",
            "register": "conversational",
            "length_band": "short",
        },
    ),
    "D17-Q17-bounded_answer": (
        {
            "user_situation_frame": "공시자료 검토 중",
            "speech_act": "자료 범위 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "향후",
            "misconception_type": "현재 정보가 미래 값을 보장한다는 전제",
            "sentence_shape": "상황절+근거범위 확인",
            "query_form": "evidence_limit",
            "register": "general",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "운용 변경 안내 확인 중",
            "speech_act": "확정 여부 확인",
            "information_gap_mode": "미래 수치 미확정 점검",
            "temporal_expression": "미래",
            "misconception_type": "미래 값이 이미 확정됐다는 전제",
            "sentence_shape": "상황절+확정전제 확인",
            "query_form": "assumption_check",
            "register": "conversational",
            "length_band": "short",
        },
        {
            "user_situation_frame": "장기 보유 계획 중",
            "speech_act": "계획 전제 점검",
            "information_gap_mode": "현재 정보와 미래 확정값 구분",
            "temporal_expression": "앞으로",
            "misconception_type": "향후 시점에도 같은 값이라는 전제",
            "sentence_shape": "계획절+정보공백 확인",
            "query_form": "planning_check",
            "register": "beginner",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "정기 점검 중",
            "speech_act": "오해 전제 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "다음",
            "misconception_type": "현재 정보가 미래 값을 보장한다는 전제",
            "sentence_shape": "상황절+확정전제 확인",
            "query_form": "assumption_check",
            "register": "general",
            "length_band": "short",
        },
    ),
    "D18-Q18-bounded_answer": (
        {
            "user_situation_frame": "공시자료 검토 중",
            "speech_act": "자료 범위 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "향후",
            "misconception_type": "미래 값이 이미 확정됐다는 전제",
            "sentence_shape": "상황절+근거범위 확인",
            "query_form": "evidence_limit",
            "register": "general",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "운용 변경 안내 확인 중",
            "speech_act": "확정 여부 확인",
            "information_gap_mode": "현재 정보와 미래 확정값 구분",
            "temporal_expression": "미래",
            "misconception_type": "현재 정보가 미래 값을 보장한다는 전제",
            "sentence_shape": "상황절+확정전제 확인",
            "query_form": "assumption_check",
            "register": "conversational",
            "length_band": "short",
        },
        {
            "user_situation_frame": "장기 보유 계획 중",
            "speech_act": "계획 전제 점검",
            "information_gap_mode": "미래 수치 미확정 점검",
            "temporal_expression": "앞으로",
            "misconception_type": "향후 시점에도 같은 값이라는 전제",
            "sentence_shape": "계획절+정보공백 확인",
            "query_form": "planning_check",
            "register": "beginner",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "계약 체결 직전",
            "speech_act": "오해 전제 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "다음",
            "misconception_type": "미래 값이 이미 확정됐다는 전제",
            "sentence_shape": "상황절+확정전제 확인",
            "query_form": "assumption_check",
            "register": "general",
            "length_band": "short",
        },
    ),
    "D20-Q12-bounded_answer": (
        {
            "user_situation_frame": "공시자료 검토 중",
            "speech_act": "자료 범위 확인",
            "information_gap_mode": "근거 범위 점검",
            "temporal_expression": "향후",
            "misconception_type": "미래 값이 이미 확정됐다는 전제",
            "sentence_shape": "상황절+근거범위 확인",
            "query_form": "evidence_limit",
            "register": "general",
            "length_band": "medium",
        },
        {
            "user_situation_frame": "장기 보유 계획 중",
            "speech_act": "계획 전제 점검",
            "information_gap_mode": "현재 정보와 미래 확정값 구분",
            "temporal_expression": "앞으로",
            "misconception_type": "현재 정보가 미래 값을 보장한다는 전제",
            "sentence_shape": "계획절+정보공백 확인",
            "query_form": "planning_check",
            "register": "conversational",
            "length_band": "short",
        },
    ),
}


def read_many(paths: tuple[Path, ...] | list[Path]) -> list[dict[str, Any]]:
    return [row for path in paths for row in bridge.read_jsonl(path)]


def promoted_passes(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return one PASS per request; a later PASS replaces an exhausted row."""
    return {row["remediation_request_id"]: row for row in bulk.distinct_pass_rows(rows)}


def latest_by_request(traces: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse repeated exhausted attempts before calculating a cell yield."""
    return {row["remediation_request_id"]: row for row in traces}


def conservative_effective_yield(passed: int, requested: int) -> float:
    """Use recent cell evidence only, reserving one observed success as risk margin."""
    if not requested or not passed:
        return 0.0
    return (passed - 1) / requested


def target_cell_audit(
    manifest_rows: list[dict[str, Any]],
    promoted: dict[str, dict[str, Any]],
    recent_traces: list[dict[str, Any]],
    reserve_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute residuals with empirical recent cell yield, never lane averaging."""
    manifest_by_id = {row["remediation_request_id"]: row for row in manifest_rows}
    latest_recent = latest_by_request(recent_traces)
    reserve_by_cell = Counter(row["coverage_cell"] for row in reserve_rows)
    results: list[dict[str, Any]] = []
    for cell in TARGET_CELLS:
        sources = [row for row in manifest_rows if row["coverage_cell"] == cell]
        if not sources:
            raise ValueError(f"target cell missing from immutable manifest: {cell}")
        source_ids = {row["remediation_request_id"] for row in sources}
        observed_ids = sorted(source_ids & set(latest_recent))
        passed = sum(request_id in promoted for request_id in observed_ids)
        requested = len(observed_ids)
        effective = conservative_effective_yield(passed, requested)
        promoted_for_cell = sum(
            row.get("coverage_cell") == cell and row.get("outcome") == "bounded_answer"
            for row in promoted.values()
        )
        residual_before_pending = max(0, sources[0]["target_count"] - sources[0]["current_pass_count"] - promoted_for_cell)
        pending_original = [row for row in sources if row["remediation_request_id"] not in promoted]
        reserve_count = reserve_by_cell[cell]
        expected_pending = (len(pending_original) + reserve_count) * effective
        residual_after_pending = max(0.0, residual_before_pending - expected_pending)
        required = math.ceil(residual_after_pending / effective) if effective else None
        safety = max(2, math.ceil(required * 0.2)) if required is not None else None
        results.append(
            {
                "coverage_cell": cell,
                "target_count": sources[0]["target_count"],
                "current_pass_count": sources[0]["current_pass_count"],
                "promoted_pass_count": promoted_for_cell,
                "cell_residual_before_pending": residual_before_pending,
                "recent_unique_requested": requested,
                "recent_unique_pass": passed,
                "recent_unique_exhausted": requested - passed,
                "recent_near_duplicate_exhausted": sum(
                    "near_duplicate_candidate" in latest_recent[request_id].get("validation_findings", [])
                    for request_id in observed_ids
                    if request_id not in promoted
                ),
                "recent_empirical_yield": round(passed / requested, 6) if requested else None,
                "effective_yield": round(effective, 6),
                "effective_yield_rule": "max(recent_unique_pass - 1, 0) / recent_unique_requested",
                "remaining_original_capacity": len(pending_original),
                "pending_v4_v5_capacity": reserve_count,
                "expected_pending_pass_at_effective_yield": round(expected_pending, 6),
                "cell_residual_after_pending": round(residual_after_pending, 6),
                "required_requests_at_effective_yield": required,
                "safety_margin_requests": safety,
                "capacity_with_safety_margin": required + safety if required is not None else None,
                "capacity_estimation_status": "estimable" if effective else "not_estimable_zero_recent_yield",
            }
        )
    return results


def build_v6_rows(manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Clone only bounded source rows and attach a fresh profile per row."""
    rows_by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        if row["coverage_cell"] in TARGET_CELLS:
            rows_by_cell[row["coverage_cell"]].append(row)
    result: list[dict[str, Any]] = []
    for cell in TARGET_CELLS:
        sources = rows_by_cell[cell]
        for offset, profile_values in enumerate(V6_PROFILES[cell], start=1):
            source = deepcopy(sources[(offset - 1) % len(sources)])
            profile = {"profile_id": f"{cell}-v6-{offset:02d}", **profile_values}
            source["buffer_source_manifest_request_id"] = source["remediation_request_id"]
            source["remediation_request_id"] = f"P49-2H-4D-C-V6-{len(result) + 1:04d}"
            source["context_frame"] = profile["user_situation_frame"]
            source["query_form"] = profile["query_form"]
            source["register"] = profile["register"]
            source["length_band"] = profile["length_band"]
            source["bounded_diversity_profile"] = {
                key: profile[key]
                for key in (
                    "profile_id",
                    "user_situation_frame",
                    "speech_act",
                    "information_gap_mode",
                    "temporal_expression",
                    "misconception_type",
                    "sentence_shape",
                )
            }
            source["v6_allocation_kind"] = "exploratory_diversity_tranche"
            source["v6_target_cell"] = cell
            result.append(source)
    return result


def control_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    profile = row["bounded_diversity_profile"]
    return (
        row["coverage_cell"],
        row["context_frame"],
        row["query_form"],
        row["register"],
        row["length_band"],
        *(profile[field] for field in (
            "user_situation_frame",
            "speech_act",
            "information_gap_mode",
            "temporal_expression",
            "misconception_type",
            "sentence_shape",
        )),
    )


def preflight(
    v6_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    comparison_questions: list[str],
    manifest_rows: list[dict[str, Any]],
    reserve_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run adapter/prompt checks and structural-control dedup with zero HCX calls."""
    failures: list[dict[str, Any]] = []
    for row in v6_rows:
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, comparison_questions)
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            if preservation or diversity:
                failures.append(
                    {
                        "remediation_request_id": row["remediation_request_id"],
                        "preservation_findings": preservation,
                        "diversity_prompt_findings": diversity,
                    }
                )
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    profile_ids = [row["bounded_diversity_profile"]["profile_id"] for row in v6_rows]
    signatures = [control_signature(row) for row in v6_rows]
    prior_control_tuples = {
        (row["coverage_cell"], row["context_frame"], row["query_form"], row["register"], row["length_band"])
        for row in [*manifest_rows, *reserve_rows]
    }
    legacy_collisions = [
        row["remediation_request_id"]
        for row in v6_rows
        if (row["coverage_cell"], row["context_frame"], row["query_form"], row["register"], row["length_band"])
        in prior_control_tuples
    ]
    return {
        "external_hcx_calls": 0,
        "requested": len(v6_rows),
        "preservation_and_prompt_pass": len(v6_rows) - len(failures),
        "failures": failures,
        "profile_ids_unique": len(profile_ids) == len(set(profile_ids)),
        "v6_control_signatures_unique": len(signatures) == len(set(signatures)),
        "legacy_four_dimension_control_collisions": legacy_collisions,
        "structural_control_dedup_pass": not legacy_collisions and len(signatures) == len(set(signatures)),
        "candidate_question_dedup_status": "not_evaluable_before_HCX_generation",
    }


def d17_neighborhood_audit(
    candidate_rows: list[dict[str, Any]],
    promoted: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Expose D17's repeated question patterns without changing dedup policy."""
    latest_candidates = {row.get("remediation_request_id"): row for row in candidate_rows if row.get("remediation_request_id")}
    d17_failed = [
        row for row in latest_candidates.values()
        if row.get("coverage_cell") == "D17-Q17-bounded_answer" and row.get("validation_status") != "pass"
    ]
    normalized_groups: dict[str, list[str]] = defaultdict(list)
    for row in d17_failed:
        normalized_groups[bridge.normalized(row["question"])].append(row["remediation_request_id"])
    repeated = [
        {"normalized_question": question, "request_ids": sorted(ids)}
        for question, ids in sorted(normalized_groups.items())
        if len(ids) > 1
    ]
    comparison = [
        row for row in promoted.values()
        if row.get("question") and row.get("remediation_request_id") not in {item["remediation_request_id"] for item in d17_failed}
    ]
    nearest: list[dict[str, Any]] = []
    for row in d17_failed:
        if comparison:
            other = max(comparison, key=lambda candidate: bridge.similarity(row["question"], candidate["question"]))
            nearest.append(
                {
                    "request_id": row["remediation_request_id"],
                    "question": row["question"],
                    "nearest_promoted_request_id": other["remediation_request_id"],
                    "similarity": round(bridge.similarity(row["question"], other["question"]), 6),
                }
            )
    return {
        "coverage_cell": "D17-Q17-bounded_answer",
        "final_failed_candidate_count": len(d17_failed),
        "near_duplicate_failed_candidate_count": sum(
            "near_duplicate_candidate" in row.get("validation_findings", []) for row in d17_failed
        ),
        "normalized_question_groups": len(normalized_groups),
        "repeated_normalized_failed_groups": repeated,
        "nearest_promoted_neighborhood": nearest,
    }


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite v6 artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--candidate", type=Path, action="append")
    parser.add_argument("--trace", type=Path, action="append")
    parser.add_argument("--recent-trace", type=Path, action="append")
    parser.add_argument("--reserve-buffer", type=Path, action="append")
    parser.add_argument("--batch-audit", type=Path, default=DEFAULT_BATCH_AUDIT)
    parser.add_argument("--expected-promoted-pass", type=int, default=294)
    parser.add_argument("--target-cushion", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    manifest_rows = bridge.read_jsonl(args.manifest)
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    candidate_rows = read_many(args.candidate or list(DEFAULT_CANDIDATES))
    promoted = promoted_passes(candidate_rows)
    if len(promoted) != args.expected_promoted_pass:
        parser.error(f"expected {args.expected_promoted_pass} promoted PASS candidates; found {len(promoted)}")
    immutable = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(immutable) != 133:
        parser.error(f"expected 133 immutable PASS candidates; found {len(immutable)}")
    traces = read_many(args.trace or list(DEFAULT_TRACES))
    recent_traces = read_many(args.recent_trace or list(DEFAULT_RECENT_TRACES))
    reserve_rows = read_many(args.reserve_buffer or list(DEFAULT_RESERVES))
    target_audit = target_cell_audit(manifest_rows, promoted, recent_traces, reserve_rows)
    v6_rows = build_v6_rows(manifest_rows)
    current_pool = [*immutable, *promoted.values()]
    preflight_audit = preflight(
        v6_rows,
        semantic_rows,
        [row["question"] for row in current_pool],
        manifest_rows,
        reserve_rows,
    )
    current_dedup = bridge.full_set_dedup_audit(current_pool, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(current_dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    batch_audit = json.loads(args.batch_audit.read_text(encoding="utf-8"))
    lane_bounded_yield = batch_audit["capacity_projection"]["observed_lane_yields"]["bounded_answer"]
    generic_target_original = sum(row["remaining_original_capacity"] * lane_bounded_yield for row in target_audit)
    generic_target_reserve = sum(row["pending_v4_v5_capacity"] * lane_bounded_yield for row in target_audit)
    empirical_target_pending = sum(row["expected_pending_pass_at_effective_yield"] for row in target_audit)
    target_adjusted_total = (
        batch_audit["capacity_projection"]["projected_total_with_reserves"]
        - generic_target_original
        - generic_target_reserve
        + empirical_target_pending
    )
    v6_expected_pass = sum(
        len(V6_PROFILES[row["coverage_cell"]]) * row["effective_yield"]
        for row in target_audit
    )
    projected_cushion = target_adjusted_total + v6_expected_pass - bulk.TARGET_TOTAL
    audit = {
        "stage": "P49-2H-4D-C bounded-targeted v6 capacity manifest",
        "external_hcx_calls": 0,
        "source_manifest": str(args.manifest),
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
        "current_accepted_quality_pool": len(current_pool),
        "promoted_4b_pass_count": len(promoted),
        "target_cells": list(TARGET_CELLS),
        "empirical_target_cell_capacity": target_audit,
        "v6_exploratory_profile_allocation": {
            cell: len(V6_PROFILES[cell]) for cell in TARGET_CELLS
        },
        "v6_manifest_rows": len(v6_rows),
        "d17_neighborhood_audit": d17_neighborhood_audit(candidate_rows, promoted),
        "preflight": preflight_audit,
        "current_pool_full_set_dedup": current_dedup,
        "current_pool_dedup_pass": collision_count == 0,
        "projection_method": {
            "baseline": "Batch-06 lane-specific capacity projection",
            "target_adjustment": "replace the four target cells' bounded lane average with recent cell effective yield",
            "zero_yield_credit": "zero; no capacity is claimed for a zero-recent-yield cell",
        },
        "baseline_projected_cushion_with_v4_v5": batch_audit["capacity_projection"]["projected_cushion_with_reserves"],
        "target_adjusted_projected_total_before_v6": round(target_adjusted_total, 6),
        "target_adjusted_projected_cushion_before_v6": round(target_adjusted_total - bulk.TARGET_TOTAL, 6),
        "v6_expected_pass_at_effective_yield": round(v6_expected_pass, 6),
        "projected_total_with_v6_at_effective_yield": round(target_adjusted_total + v6_expected_pass, 6),
        "projected_cushion_with_v6_at_effective_yield": round(projected_cushion, 6),
        "target_cushion": args.target_cushion,
        "capacity_go": projected_cushion >= args.target_cushion,
        "v6_execution_allowed": False,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in v6_rows))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "external_hcx_calls": 0,
                "v6_manifest_rows": len(v6_rows),
                "current_accepted_quality_pool": len(current_pool),
                "preflight_pass": preflight_audit["preservation_and_prompt_pass"],
                "capacity_go": audit["capacity_go"],
                "projected_cushion": audit["projected_cushion_with_v6_at_effective_yield"],
                "output": str(args.output),
                "audit_output": str(args.audit_output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
