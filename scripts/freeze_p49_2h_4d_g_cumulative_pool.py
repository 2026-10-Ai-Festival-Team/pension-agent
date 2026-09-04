"""Freeze the reconciled P49-2H-4D cumulative 532-PASS comparison baseline.

Batch-07's raw 31 PASS rows include three IDs already canonically promoted as
historical 5A replacements.  A naive 435 + 16 + 50 + 31 sum therefore produces
532 by counting those identities twice. This local-only reconciliation keeps
the historical 5A rows as canonical, excludes their duplicate Batch-07 retry
rows from incremental credit, reruns complete dedup, and records every
artifact contribution without changing any source candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge


class Source:
    """Small importlib-safe source descriptor for Python 3.9 test loading."""

    def __init__(self, name: str, path: Path, expected_pass: int, accounting_role: str) -> None:
        self.name = name
        self.path = path
        self.expected_pass = expected_pass
        self.accounting_role = accounting_role


SOURCES = (
    Source("immutable_3f", bridge.COMPARISON_POOL, 133, "immutable_base"),
    Source("4c_smoke", ROOT / "evaluation/fine_tuning/p49_2h_4c_3_smoke_candidates_v1.jsonl", 10, "validated_bridge_pass"),
    Source("4c_retry", ROOT / "evaluation/fine_tuning/p49_2h_4c_3_retry_candidates_v1.jsonl", 2, "validated_bridge_retry_pass"),
    Source("4d_batch_01", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_candidates_v1.jsonl", 63, "bulk_pass"),
    Source("4d_batch_02", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_02_candidates_v1.jsonl", 60, "bulk_pass"),
    Source("4d_batch_03", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_03_candidates_v1.jsonl", 45, "bulk_pass"),
    Source("4d_batch_04", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_04_candidates_v1.jsonl", 44, "bulk_pass"),
    Source("4d_batch_05", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_05_candidates_v1.jsonl", 36, "bulk_pass"),
    Source("4d_batch_06", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_06_candidates_v1.jsonl", 31, "bulk_pass"),
    # These three 5A same-contract replacements were already included in the
    # 435 baseline used by E2. They are listed explicitly so that a future
    # runner cannot silently omit their accounting scope again.
    Source("5a_same_record", ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_same_record_retest_candidates_v1.jsonl", 2, "historical_replacement_pass"),
    Source("5a_neighbor", ROOT / "evaluation/fine_tuning/p49_2h_4d_5a_neighbor_candidates_v1.jsonl", 1, "historical_replacement_pass"),
    Source("anchor_smoke", ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_promoted_v1.jsonl", 8, "promoted_anchor_pass"),
    Source("e2_logical_promotion", ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_quality_gate_promoted_v1.jsonl", 16, "promoted_logical_replacement_pass"),
    Source("f_register", ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_candidates_v1.jsonl", 49, "logical_register_pass"),
    Source("f1a_replacement", ROOT / "evaluation/fine_tuning/p49_2h_4d_f1a_generation_retry_candidates_v1.jsonl", 1, "logical_operational_replacement_pass"),
    Source("4d_batch_07", ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_07_candidates_v1.jsonl", 31, "bulk_pass"),
)
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g_cumulative_comparison_pool_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g_cumulative_pool_accounting_audit_v1.json"
HISTORICAL_5A_RETRY_IDS = frozenset({
    "P49-2H-4B-0158",
    "P49-2H-4B-0159",
    "P49-2H-4B-0207",
})


def identity(row: dict[str, Any]) -> str:
    value = row.get("remediation_request_id") or row.get("candidate_id") or row.get("full_request_id")
    if not value:
        raise ValueError("PASS candidate has no stable identity")
    return str(value)


def read_passes(source: Source) -> list[dict[str, Any]]:
    rows = [row for row in bridge.read_jsonl(source.path) if row.get("validation_status") == "pass"]
    if len(rows) != source.expected_pass:
        raise ValueError(f"{source.name} expected {source.expected_pass} PASS rows; found {len(rows)}")
    local_ids = [identity(row) for row in rows]
    if len(local_ids) != len(set(local_ids)):
        raise ValueError(f"{source.name} contains duplicate PASS identities")
    return rows


def reconcile(sources: tuple[Source, ...] = SOURCES) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    contributions: list[dict[str, Any]] = []
    historical_retry_exclusions: list[dict[str, str]] = []
    for source in sources:
        rows = read_passes(source)
        effective_rows = rows
        cross_duplicates = [identity(row) for row in rows if identity(row) in seen]
        if cross_duplicates:
            if source.name != "4d_batch_07" or set(cross_duplicates) != HISTORICAL_5A_RETRY_IDS:
                raise ValueError(f"{source.name} duplicates existing pool identity: {cross_duplicates[0]}")
            effective_rows = [row for row in rows if identity(row) not in HISTORICAL_5A_RETRY_IDS]
            historical_retry_exclusions.extend({
                "batch_07_request_id": request_id,
                "canonical_historical_owner": seen[request_id],
                "exclusion_reason": "same remediation_request_id already canonically counted as a 5A replacement",
            } for request_id in sorted(cross_duplicates))
        for row in effective_rows:
            seen[identity(row)] = source.name
        pool.extend(effective_rows)
        contributions.append({
            "artifact": source.name,
            "path": str(source.path),
            "sha256": hashlib.sha256(source.path.read_bytes()).hexdigest(),
            "accounting_role": source.accounting_role,
            "raw_pass_count": len(rows),
            "effective_unique_pass_contribution": len(effective_rows),
            "cumulative_after": len(pool),
        })
    expected_total = 529
    if len(pool) != expected_total:
        raise AssertionError(f"reconciled comparison pool expected {expected_total}; found {len(pool)}")
    dedup = bridge.full_set_dedup_audit(pool, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    audit = {
        "stage": "P49-2H-4D-G Cumulative PASS Accounting Reconciliation",
        "external_hcx_calls": 0,
        "accounting_issue": "The apparent 529 vs 532 discrepancy comes from three Batch-07 raw PASS rows whose remediation IDs were already counted in the historical 5A replacement portion of the 435 pre-E2 pool.",
        "accounting_resolution": "Keep 5A same-record (2) and neighbor (1) rows as canonical historical owners; exclude their duplicate Batch-07 retries from incremental PASS credit. No candidate source artifact is modified.",
        "prior_reported_count": 529,
        "reconciled_count": len(pool),
        "naive_double_counted_total": 532,
        "duplicate_historical_retry_count": len(historical_retry_exclusions),
        "historical_retry_exclusions": historical_retry_exclusions,
        "artifact_contributions": contributions,
        "unique_candidate_identity_count": len(seen),
        "cross_artifact_duplicate_id_count": len(historical_retry_exclusions),
        "cumulative_full_set_dedup": dedup,
        "cumulative_full_set_dedup_pass": collision_count == 0,
        "batch_08_original_manifest_allowed": False,
        "bounded_targeted_anchor_recovery_allowed": collision_count == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    return pool, audit


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite accounting-freeze artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    pool, audit = reconcile()
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in pool))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "prior_reported_count": audit["prior_reported_count"],
        "reconciled_count": audit["reconciled_count"],
        "naive_double_counted_total": audit["naive_double_counted_total"],
        "duplicate_historical_retry_count": audit["duplicate_historical_retry_count"],
        "dedup_pass": audit["cumulative_full_set_dedup_pass"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
