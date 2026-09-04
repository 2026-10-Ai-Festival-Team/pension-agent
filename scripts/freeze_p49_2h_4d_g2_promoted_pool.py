"""Promote the strict-G2 bounded PASS tranche into a new 537-PASS pool.

The preceding 529 comparison pool is immutable.  This script creates a new
additive promotion artifact and a new comparison pool only after checking the
G2 strict gate, stable identities, and the unchanged full-set dedup route.
It never calls HCX and never edits either source artifact.
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


BASELINE_529 = ROOT / "evaluation/fine_tuning/p49_2h_4d_g_cumulative_comparison_pool_v1.jsonl"
G2_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_candidates_v1.jsonl"
G2_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_audit_v1.json"
DEFAULT_PROMOTION = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_promoted_v1.jsonl"
DEFAULT_POOL = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_cumulative_comparison_pool_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_promotion_audit_v1.json"


def identity(row: dict[str, Any]) -> str:
    value = row.get("remediation_request_id") or row.get("candidate_id") or row.get("full_request_id")
    if not value:
        raise ValueError("candidate has no stable identity")
    return str(value)


def promote(baseline: list[dict[str, Any]], g2_candidates: list[dict[str, Any]], g2_audit: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return additive G2 promotion rows, frozen 537 pool, and audit payload."""
    if len(baseline) != 529 or any(row.get("validation_status") != "pass" for row in baseline):
        raise ValueError("expected exactly 529 validated PASS records in prior baseline")
    required_gate = (
        g2_audit.get("strict_tranche_quality_go") is True
        and g2_audit.get("anchor_space_validation_go") is True
        and g2_audit.get("promotion_allowed") is True
        and g2_audit.get("cumulative_full_set_dedup_pass") is True
        and g2_audit.get("semantic_evidence_outcome_pass") == 8
        and g2_audit.get("d30_unique_pass") == 4
        and not g2_audit.get("validation_findings")
        and not g2_audit.get("new_failure_classes")
    )
    if not required_gate:
        raise ValueError("G2 strict promotion gate is not closed")
    promoted = [row for row in g2_candidates if row.get("validation_status") == "pass"]
    if len(promoted) != 8:
        raise ValueError(f"expected exactly 8 G2 PASS candidates; found {len(promoted)}")
    baseline_ids = {identity(row) for row in baseline}
    promoted_ids = [identity(row) for row in promoted]
    if len(promoted_ids) != len(set(promoted_ids)):
        raise ValueError("G2 promotion contains duplicate identities")
    overlap = sorted(baseline_ids & set(promoted_ids))
    if overlap:
        raise ValueError(f"G2 identities already exist in 529 baseline: {overlap[0]}")
    pool = [*baseline, *promoted]
    dedup = bridge.full_set_dedup_audit(pool, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(len(dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    audit = {
        "stage": "P49-2H-4D-G2 bounded anchor promotion / 537 baseline freeze",
        "external_hcx_calls": 0,
        "prior_comparison_pool_count": len(baseline),
        "g2_promoted_pass_count": len(promoted),
        "new_comparison_pool_count": len(pool),
        "g2_strict_gate_closed": required_gate,
        "g2_candidate_ids": promoted_ids,
        "cross_pool_identity_overlap": overlap,
        "full_537_set_dedup": dedup,
        "full_537_set_dedup_pass": collision_count == 0,
        "bounded_delta": 8,
        "bounded_current_unique_pass": 67,
        "bounded_target": 102,
        "bounded_remaining_deficit": 35,
        "overall_remaining_to_600": 63,
        "batch_08_original_manifest_allowed": False,
        "g3_bounded_residual_recovery_allowed": collision_count == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    return promoted, pool, audit


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite immutable G2 promotion artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE_529)
    parser.add_argument("--g2-candidates", type=Path, default=G2_CANDIDATES)
    parser.add_argument("--g2-audit", type=Path, default=G2_AUDIT)
    parser.add_argument("--promotion-output", type=Path, default=DEFAULT_PROMOTION)
    parser.add_argument("--pool-output", type=Path, default=DEFAULT_POOL)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    promoted, pool, audit = promote(
        bridge.read_jsonl(args.baseline), bridge.read_jsonl(args.g2_candidates),
        json.loads(args.g2_audit.read_text(encoding="utf-8")),
    )
    audit.update({
        "prior_comparison_pool": str(args.baseline),
        "prior_comparison_pool_sha256": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        "prior_comparison_pool_modified": False,
        "g2_candidates": str(args.g2_candidates),
        "g2_candidates_sha256": hashlib.sha256(args.g2_candidates.read_bytes()).hexdigest(),
        "g2_audit": str(args.g2_audit),
    })
    write_new(args.promotion_output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in promoted))
    write_new(args.pool_output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in pool))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "prior_comparison_pool_count": audit["prior_comparison_pool_count"],
        "g2_promoted_pass_count": audit["g2_promoted_pass_count"],
        "new_comparison_pool_count": audit["new_comparison_pool_count"],
        "full_537_set_dedup_pass": audit["full_537_set_dedup_pass"],
        "bounded_remaining_deficit": audit["bounded_remaining_deficit"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
