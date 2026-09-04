"""Promote the closed E2 logical tranche without overwriting E2/E2A history.

The original E2 row ``...0007`` remains generation_exhausted forever.  Its
E2A result is included only as an explicitly declared logical replacement in
this additive quality-pool artifact.  Promotion is not acceptance, export, or
tuning.
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

from scripts import close_p49_2h_4d_e2_quality_gate as closure


DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_quality_gate_promoted_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_quality_gate_promotion_audit_v1.json"


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2 promotion artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def logical_e2_rows() -> list[dict[str, Any]]:
    """Return the 15 original E2 PASS rows plus the one E2A replacement."""
    e2_rows = closure.read_jsonl(closure.E2_CANDIDATES)
    e2a_rows = closure.read_jsonl(closure.E2A_CANDIDATES)
    original = closure._single(e2_rows, closure.TARGET_E2_ID, "E2 target candidate")
    replacement = closure._single(e2a_rows, closure.TARGET_E2A_ID, "E2A replacement candidate")
    if original.get("generation_status") != "generation_exhausted":
        raise ValueError("E2 promotion requires the original target to remain generation_exhausted")
    if replacement.get("validation_status") != "pass":
        raise ValueError("E2 promotion requires a validated E2A replacement")

    rows = [deepcopy(row) for row in e2_rows if row["remediation_request_id"] != closure.TARGET_E2_ID]
    if len(rows) != 15 or any(row.get("validation_status") != "pass" for row in rows):
        raise ValueError("E2 promotion requires 15 original validated E2 PASS candidates")
    rows.append(deepcopy(replacement))
    if len({row["remediation_request_id"] for row in rows}) != 16:
        raise ValueError("logical E2 promotion must have sixteen distinct request IDs")

    for row in rows:
        replacement_for = closure.TARGET_E2_ID if row["remediation_request_id"] == closure.TARGET_E2A_ID else None
        row["quality_pool_promotion_status"] = "promoted_validation_pass"
        row["quality_pool_promotion_scope"] = "additive_comparison_pool_only"
        row["quality_pool_promotion_is_acceptance"] = False
        row["logical_e2_lineage"] = {
            "logical_tranche": "P49-2H-4D-E2",
            "original_e2_candidate_count": 16,
            "original_e2_validation_pass_count": 15,
            "closure_route": "P49-2H-4D-E2A supported answer omission repair",
            "logical_replacement_for_request_id": replacement_for,
            "original_exhausted_request_id": closure.TARGET_E2_ID if replacement_for else None,
            "replacement_request_id": closure.TARGET_E2A_ID if replacement_for else None,
        }
    return rows


def promotion_audit(rows: list[dict[str, Any],], closure_audit: dict[str, Any]) -> dict[str, Any]:
    if not closure_audit.get("e2_full_quality_gate_go") or not closure_audit.get("register_taxonomy_quality_gate_go"):
        raise ValueError("E2 quality-gate closure does not authorize promotion")
    if closure_audit.get("promotion_eligible_pass_count") != 16:
        raise ValueError("E2 closure promotion count is not sixteen")
    if closure_audit.get("comparison_pool_before") != 435:
        raise ValueError("E2 promotion must begin from the fixed 435-PASS pool")
    if len(rows) != 16:
        raise ValueError("E2 promotion must contain sixteen logical PASS candidates")
    return {
        "stage": "P49-2H-4D-E2 Logical Quality-Pool Promotion",
        "external_hcx_calls": 0,
        "closure_audit": str(closure.DEFAULT_OUTPUT),
        "closure_audit_sha256": hashlib.sha256(closure.DEFAULT_OUTPUT.read_bytes()).hexdigest(),
        "source_e2_candidates": str(closure.E2_CANDIDATES),
        "source_e2a_candidates": str(closure.E2A_CANDIDATES),
        "source_artifacts_modified": False,
        "quality_pool_before": 435,
        "promoted_validation_pass_count": len(rows),
        "promoted_request_ids": [row["remediation_request_id"] for row in rows],
        "quality_pool_after": 451,
        "logical_e2_lineage": {
            "original_e2_pass_count": 15,
            "original_e2_exhausted_request_id": closure.TARGET_E2_ID,
            "e2a_replacement_request_id": closure.TARGET_E2A_ID,
            "logical_e2_pass_count": 16,
            "original_candidate_overwritten": False,
        },
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    rows = logical_e2_rows()
    closure_audit = json.loads(closure.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    audit = promotion_audit(rows, closure_audit)
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "promoted_validation_pass_count": audit["promoted_validation_pass_count"],
        "quality_pool_after": audit["quality_pool_after"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
