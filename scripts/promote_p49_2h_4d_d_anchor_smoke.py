"""Promote only validated P49-2H-4D-D anchor-smoke PASS candidates.

Promotion here means inclusion in the additive quality-comparison pool.  It is
not acceptance, export, tuning, or a modification of the frozen 4B manifest.
The script refuses a smoke result unless its audit verified bridge health,
D17 recovery, zero new failure classes, and clean full-set dedup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge


DEFAULT_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_candidates_v1.jsonl"
DEFAULT_SMOKE_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_audit_v1.json"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_promoted_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_promotion_audit_v1.json"


def promoted_rows(candidates: list[dict[str, Any]], smoke_audit: dict[str, Any]) -> list[dict[str, Any]]:
    if not smoke_audit.get("promotion_allowed"):
        raise ValueError("anchor-smoke audit does not authorize quality-pool promotion")
    passes = [deepcopy(row) for row in candidates if row.get("validation_status") == "pass"]
    if len(passes) != smoke_audit.get("promotion_eligible_pass_count"):
        raise ValueError("candidate PASS count does not match smoke promotion audit")
    if not passes:
        raise ValueError("no validated anchor-smoke PASS candidates to promote")
    ids = [row.get("remediation_request_id") for row in passes]
    if len(ids) != len(set(ids)) or any(not request_id for request_id in ids):
        raise ValueError("promoted candidates must have distinct remediation request IDs")
    for row in passes:
        row["quality_pool_promotion_status"] = "promoted_validation_pass"
        row["quality_pool_promotion_scope"] = "additive_comparison_pool_only"
        row["quality_pool_promotion_is_acceptance"] = False
    return passes


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite anchor-smoke promotion artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--smoke-audit", type=Path, default=DEFAULT_SMOKE_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    candidates = bridge.read_jsonl(args.candidates)
    smoke_audit = json.loads(args.smoke_audit.read_text(encoding="utf-8"))
    promoted = promoted_rows(candidates, smoke_audit)
    audit = {
        "stage": "P49-2H-4D-D Anchor Smoke Quality-Pool Promotion",
        "external_hcx_calls": 0,
        "source_candidates": str(args.candidates),
        "source_candidates_sha256": hashlib.sha256(args.candidates.read_bytes()).hexdigest(),
        "source_smoke_audit": str(args.smoke_audit),
        "source_smoke_audit_sha256": hashlib.sha256(args.smoke_audit.read_bytes()).hexdigest(),
        "source_artifacts_modified": False,
        "promoted_validation_pass_count": len(promoted),
        "promoted_request_ids": [row["remediation_request_id"] for row in promoted],
        "quality_pool_before": smoke_audit["cumulative_quality_pool_before"],
        "quality_pool_after": smoke_audit["cumulative_quality_pool_if_promoted"],
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in promoted))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "promoted_validation_pass_count": len(promoted),
        "quality_pool_after": audit["quality_pool_after"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
