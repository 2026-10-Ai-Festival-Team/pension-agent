"""Build an additive P49-2H-4D-B capacity-buffer manifest with zero HCX calls.

The frozen 468-row 4B manifest is read-only.  This builder calculates each
coverage cell's expected remaining shortfall from current PASS records,
pending original-manifest capacity, and observed lane-specific batch
yields, then emits a separate capacity artifact.  It creates no candidates and
does not authorize buffer HCX execution.
"""
from __future__ import annotations

import argparse
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
from scripts.p49_2h_register_taxonomy import REGISTER_ALLOCATION_CYCLE, register_for_index


MANIFEST = bridge.REMEDIATION_MANIFEST
COMPARISON_POOL = bridge.COMPARISON_POOL
DEFAULT_CANDIDATE_PATHS = (
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_smoke_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_retry_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_02_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_03_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_04_candidates_v1.jsonl",
)
DEFAULT_OBSERVED_AUDITS = (
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_cumulative_audit_v2.json",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_02_cumulative_audit_v1.json",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_03_cumulative_audit_v1.json",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_04_cumulative_audit_v1.json",
)
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_buffer_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_buffer_v1.json"

LANE_ORDER = ("supported_answer", "clarification_required", "bounded_answer")
DEFAULT_EXPECTED_PROMOTED_PASS = 224
FRAMES = ("이직/퇴직 직후", "이전 신청 중", "상담 전 확인", "상품 비교 전 확인", "세액공제 계산 전", "서류 준비 중")
FORMS = ("direct", "confirmation", "misconception", "conditional", "numeric")
# New additive capacity artifacts use the shared policy; existing v1-v5
# artifacts remain frozen and are not rewritten.
REGISTERS = REGISTER_ALLOCATION_CYCLE
LENGTHS = ("short", "medium")


def read_many(paths: list[Path] | tuple[Path, ...]) -> list[dict[str, Any]]:
    return [row for path in paths for row in bridge.read_jsonl(path)]


def distinct_pass_by_request(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return exactly one promoted PASS per 4B request; exhausted attempts remain pending."""
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("validation_status") != "pass" or not row.get("remediation_request_id"):
            continue
        request_id = row["remediation_request_id"]
        if request_id in result:
            raise ValueError(f"multiple PASS rows for remediation request {request_id}")
        result[request_id] = row
    return result


def lane_yields(observed_audits: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate recorded lane results; never substitute one overall yield."""
    requested = Counter()
    passed = Counter()
    for observed_audit in observed_audits:
        requested.update(observed_audit["outcome_requested"])
        passed.update(observed_audit["outcome_pass"])
    if any(requested.get(lane, 0) <= 0 for lane in LANE_ORDER):
        raise ValueError("observed audits must contain requested records for every outcome lane")
    yields = {lane: passed[lane] / requested[lane] for lane in LANE_ORDER}
    return yields


def cell_capacity(
    manifest_rows: list[dict[str, Any]],
    promoted: dict[str, dict[str, Any]],
    observed_lane_yields: dict[str, float],
) -> list[dict[str, Any]]:
    """Calculate expected residual capacity per immutable outcome × coverage cell."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in manifest_rows:
        groups[row["target_outcome"], row["coverage_cell"]].append(row)
    promoted_by_cell = Counter((row["outcome"], row["coverage_cell"]) for row in promoted.values())
    capacities: list[dict[str, Any]] = []
    for (lane, coverage_cell), rows in sorted(groups.items()):
        original_current = rows[0]["current_pass_count"]
        target_count = rows[0]["target_count"]
        pass_count = promoted_by_cell[lane, coverage_cell]
        pending = [row for row in rows if row["remediation_request_id"] not in promoted]
        yield_rate = observed_lane_yields[lane]
        expected_pending_pass = len(pending) * yield_rate
        expected_residual = max(0.0, target_count - (original_current + pass_count + expected_pending_pass))
        capacities.append(
            {
                "outcome": lane,
                "coverage_cell": coverage_cell,
                "target_count": target_count,
                "current_pass_count": original_current + pass_count,
                "promoted_pass_count": pass_count,
                "pending_existing_capacity": len(pending),
                "observed_lane_yield": yield_rate,
                "expected_existing_pending_pass": expected_pending_pass,
                "expected_residual_deficit": expected_residual,
                "source_rows": pending or rows,
            }
        )
    return capacities


def account_for_planned_buffer(
    capacities: list[dict[str, Any]],
    planned_buffer_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Subtract the expected cell contribution of preserved buffer artifacts.

    A later additive buffer must not treat an earlier, still-planned buffer as
    nonexistent.  The original capacity rows are left untouched so prior audit
    artifacts remain reproducible.
    """
    planned_by_cell = Counter(
        (row["target_outcome"], row["coverage_cell"])
        for row in planned_buffer_rows
    )
    adjusted: list[dict[str, Any]] = []
    for row in capacities:
        updated = dict(row)
        key = row["outcome"], row["coverage_cell"]
        planned_count = planned_by_cell[key]
        planned_expected_pass = planned_count * row["observed_lane_yield"]
        updated["expected_residual_deficit_before_planned_buffer"] = row["expected_residual_deficit"]
        updated["planned_buffer_capacity"] = planned_count
        updated["planned_buffer_expected_pass"] = planned_expected_pass
        updated["expected_residual_deficit"] = max(
            0.0,
            row["expected_residual_deficit"] - planned_expected_pass,
        )
        adjusted.append(updated)
    return adjusted


def allocate_buffer(capacities: list[dict[str, Any]], capacity: int) -> dict[tuple[str, str], int]:
    """Allocate additive requests by residual deficit, then lane-specific risk.

    Each unit first goes to the cell with the largest uncovered expected
    deficit.  Once all expected deficits are covered, remaining cushion goes
    to the same risk-ranked cells, with lower observed lane yield receiving
    priority.  This avoids an overall-yield allocation that would underfund
    clarification requests.
    """
    if capacity <= 0:
        raise ValueError("buffer capacity must be positive")
    allocations = {(row["outcome"], row["coverage_cell"]): 0 for row in capacities}
    by_key = {(row["outcome"], row["coverage_cell"]): row for row in capacities}
    for _ in range(capacity):
        def priority(key: tuple[str, str]) -> tuple[float, float, str]:
            row = by_key[key]
            uncovered = row["expected_residual_deficit"] - allocations[key] * row["observed_lane_yield"]
            if uncovered > 0:
                return (uncovered, 1 - row["observed_lane_yield"], key[1])
            risk = (row["expected_residual_deficit"] + 0.01) * (1 - row["observed_lane_yield"] + 0.05)
            return (risk, 1 - row["observed_lane_yield"], key[1])
        target = max(allocations, key=priority)
        allocations[target] += 1
    return allocations


def build_buffer_rows(
    capacities: list[dict[str, Any]],
    allocations: dict[tuple[str, str], int],
    *,
    id_prefix: str = "P49-2H-4D-B",
) -> list[dict[str, Any]]:
    """Clone only semantic/provenance-bound source rows into a new additive manifest."""
    buffer_rows: list[dict[str, Any]] = []
    for capacity_row in capacities:
        key = capacity_row["outcome"], capacity_row["coverage_cell"]
        allocated = allocations[key]
        source_rows = capacity_row["source_rows"]
        for offset in range(allocated):
            source = deepcopy(source_rows[offset % len(source_rows)])
            source["buffer_source_manifest_request_id"] = source["remediation_request_id"]
            source["buffer_priority_rank"] = None  # assigned after global ranking
            source["buffer_allocation_for_cell"] = allocated
            source["observed_lane_yield"] = capacity_row["observed_lane_yield"]
            source["expected_existing_pending_pass"] = capacity_row["expected_existing_pending_pass"]
            source["expected_residual_deficit"] = capacity_row["expected_residual_deficit"]
            source["current_pass_count"] = capacity_row["current_pass_count"]
            source["deficit_count"] = math.ceil(capacity_row["expected_residual_deficit"])
            # New controls change only the model-owned question wording. Every
            # semantic/evidence/provenance field remains copied from the 4B
            # source row, and the original 468-row manifest is untouched.
            control_index = len(buffer_rows)
            source["context_frame"] = FRAMES[control_index % len(FRAMES)]
            source["query_form"] = FORMS[control_index % len(FORMS)]
            source["register"] = register_for_index(control_index)
            source["length_band"] = LENGTHS[control_index % len(LENGTHS)]
            buffer_rows.append(source)
    ranked = sorted(
        buffer_rows,
        key=lambda row: (
            -row["expected_residual_deficit"],
            row["observed_lane_yield"],
            row["coverage_cell"],
            row["buffer_source_manifest_request_id"],
        ),
    )
    for index, row in enumerate(ranked, start=1):
        row["remediation_request_id"] = f"{id_prefix}-{index:04d}"
        row["buffer_priority_rank"] = index
    return ranked


def report(
    capacities: list[dict[str, Any]],
    allocations: dict[tuple[str, str], int],
    buffer_rows: list[dict[str, Any]],
    promoted: dict[str, dict[str, Any]],
    observed_yields: dict[str, float],
    observed_audit_paths: list[Path],
    planned_buffer_paths: list[Path],
    planned_buffer_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total_expected_residual = sum(row["expected_residual_deficit"] for row in capacities)
    expected_buffer_pass = sum(
        allocation * next(row["observed_lane_yield"] for row in capacities if (row["outcome"], row["coverage_cell"]) == key)
        for key, allocation in allocations.items()
    )
    by_lane = Counter(row["target_outcome"] for row in buffer_rows)
    cell_rows = [
        {
            key: value
            for key, value in row.items()
            if key != "source_rows"
        }
        | {"buffer_allocation": allocations[row["outcome"], row["coverage_cell"]]}
        for row in capacities
        if allocations[row["outcome"], row["coverage_cell"]]
    ]
    return {
        "stage": "P49-2H-4D-B Capacity Buffer Manifest",
        "external_hcx_calls": 0,
        "source_manifest": str(MANIFEST),
        "source_manifest_modified": False,
        "promoted_pass_count": len(promoted),
        "observed_lane_yields": observed_yields,
        "observed_audits": [str(path) for path in observed_audit_paths],
        "planned_buffer_artifacts": [str(path) for path in planned_buffer_paths],
        "planned_buffer_rows": len(planned_buffer_rows),
        "planned_buffer_expected_pass_at_observed_lane_yields": round(
            sum(row["planned_buffer_expected_pass"] for row in capacities),
            6,
        ),
        "expected_residual_before_planned_buffer": round(
            sum(row.get("expected_residual_deficit_before_planned_buffer", row["expected_residual_deficit"]) for row in capacities),
            6,
        ),
        "recommended_capacity": len(buffer_rows),
        "buffer_rows": len(buffer_rows),
        "buffer_outcome_counts": {lane: by_lane[lane] for lane in LANE_ORDER},
        "expected_residual_deficit_before_buffer": round(total_expected_residual, 6),
        "expected_buffer_pass_at_observed_lane_yields": round(expected_buffer_pass, 6),
        "allocation_by_cell": cell_rows,
        "buffer_hcx_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing buffer artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--candidate", type=Path, action="append", help="Validated candidate JSONL; defaults to 4C plus Batch-01 through Batch-04 artifacts.")
    parser.add_argument("--observed-audit", type=Path, action="append", help="Batch audit used for aggregate lane-specific yield; defaults to Batch-01 through Batch-04.")
    parser.add_argument("--planned-buffer", type=Path, action="append", help="Preserved additive buffer manifest whose expected cell capacity must be counted before allocating this new buffer.")
    parser.add_argument("--expected-promoted-pass", type=int, default=DEFAULT_EXPECTED_PROMOTED_PASS, help="Exact PASS count expected from --candidate inputs.")
    parser.add_argument("--capacity", type=int, default=100)
    parser.add_argument("--id-prefix", default="P49-2H-4D-B", help="Prefix for new additive remediation request IDs.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    if args.capacity <= 0:
        parser.error("buffer capacity must be positive")

    manifest_rows = bridge.read_jsonl(args.manifest)
    immutable_pass = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(immutable_pass) != 133:
        parser.error(f"expected 133 immutable PASS rows, found {len(immutable_pass)}")
    candidate_paths = args.candidate or list(DEFAULT_CANDIDATE_PATHS)
    promoted = distinct_pass_by_request(read_many(candidate_paths))
    if len(promoted) != args.expected_promoted_pass:
        parser.error(f"expected {args.expected_promoted_pass} promoted PASS rows, found {len(promoted)}")
    observed_audit_paths = args.observed_audit or list(DEFAULT_OBSERVED_AUDITS)
    yields = lane_yields([json.loads(path.read_text(encoding="utf-8")) for path in observed_audit_paths])
    capacities = cell_capacity(manifest_rows, promoted, yields)
    planned_buffer_paths = args.planned_buffer or []
    planned_buffer_rows = read_many(planned_buffer_paths)
    if planned_buffer_rows:
        capacities = account_for_planned_buffer(capacities, planned_buffer_rows)
    allocations = allocate_buffer(capacities, args.capacity)
    buffer_rows = build_buffer_rows(capacities, allocations, id_prefix=args.id_prefix)
    if len(buffer_rows) != args.capacity or len({row["remediation_request_id"] for row in buffer_rows}) != args.capacity:
        raise AssertionError("buffer manifest capacity or ID uniqueness failed")
    planned_ids = {row["remediation_request_id"] for row in planned_buffer_rows}
    if planned_ids & {row["remediation_request_id"] for row in buffer_rows}:
        raise AssertionError("new additive buffer IDs overlap a preserved buffer artifact")
    output = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in buffer_rows)
    audit = report(
        capacities,
        allocations,
        buffer_rows,
        promoted,
        yields,
        observed_audit_paths,
        planned_buffer_paths,
        planned_buffer_rows,
    )
    write_new(args.output, output)
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "external_hcx_calls": 0,
                "buffer_rows": len(buffer_rows),
                "buffer_outcome_counts": audit["buffer_outcome_counts"],
                "observed_lane_yields": yields,
                "output": str(args.output),
                "audit_output": str(args.audit_output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
