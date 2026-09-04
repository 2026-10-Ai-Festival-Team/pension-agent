"""Finalize explicitly approved P49-2H-4D-D linguistic anchors.

This only promotes an immutable copy of the reviewed draft artifact.  It does
not edit the draft, the source remediation manifest, or any gold artifact, and
it never calls HCX.  The resulting artifact may be used by the existing bridge
for the separately authorized eight-record anchor smoke.
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

from scripts import build_p49_2h_4d_bounded_targeted_v6 as v6
from scripts import build_p49_2h_4d_d_linguistic_anchor_pilot as pilot
from scripts import run_p49_2h_4c_execution_bridge as bridge


DEFAULT_INPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_drafts_v2.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_human_approved_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_human_approved_audit_v1.json"


def approve_rows(draft_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Promote only the exact reviewed set; reject any ambiguous source state."""
    if len(draft_rows) != 12:
        raise ValueError(f"expected exactly 12 reviewed anchor drafts; found {len(draft_rows)}")
    approved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for draft in draft_rows:
        row = deepcopy(draft)
        request_id = row.get("remediation_request_id")
        if not isinstance(request_id, str) or request_id in seen_ids:
            raise ValueError(f"invalid or duplicate remediation_request_id: {request_id!r}")
        seen_ids.add(request_id)
        anchor = row.get("bounded_linguistic_anchor")
        if not isinstance(anchor, dict):
            raise ValueError(f"missing bounded_linguistic_anchor for {request_id}")
        if anchor.get("authoring_status") != "drafted_by_codex":
            raise ValueError(f"unexpected authoring status for {request_id}: {anchor.get('authoring_status')!r}")
        if anchor.get("human_review_status") != "human_review_required":
            raise ValueError(f"unexpected review status for {request_id}: {anchor.get('human_review_status')!r}")
        if row.get("anchor_pilot_status") != "draft_pending_human_review":
            raise ValueError(f"unexpected pilot status for {request_id}: {row.get('anchor_pilot_status')!r}")
        anchor["authoring_status"] = "human_written"
        anchor["human_review_status"] = "human_approved"
        anchor["approval_provenance"] = "explicit_user_approval"
        row["anchor_pilot_status"] = "human_written_human_approved"
        approved.append(row)
    return approved


def approved_preflight(
    approved_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    comparison_questions: list[str],
) -> dict[str, Any]:
    """Reuse the draft preflight, then record the approved execution gate."""
    report = pilot.preflight(approved_rows, semantic_rows, comparison_questions)
    return {
        "external_hcx_calls": 0,
        "requested": report["requested"],
        "preservation_prompt_and_semantic_pass": report["preservation_prompt_and_semantic_pass"],
        "failures": report["failures"],
        "human_written_human_approved": len(approved_rows),
        "hcx_execution_allowed": not report["failures"],
    }


def full_set_dedup(
    approved_rows: list[dict[str, Any]],
    current_pool: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    inputs = [
        {
            "remediation_request_id": row["remediation_request_id"],
            "validation_status": "pass",
            "generation_status": "not_generated_human_approved_anchor",
            "question": row["bounded_linguistic_anchor"]["anchor_question"],
        }
        for row in approved_rows
    ]
    return bridge.full_set_dedup_audit(current_pool, inputs, bridge.read_jsonl(bridge.FROZEN_SEED))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--candidate", type=Path, action="append")
    parser.add_argument("--expected-promoted-pass", type=int, default=294)
    args = parser.parse_args()

    draft_rows = bridge.read_jsonl(args.input)
    approved_rows = approve_rows(draft_rows)
    candidate_rows = v6.read_many(args.candidate or list(v6.DEFAULT_CANDIDATES))
    promoted = v6.promoted_passes(candidate_rows)
    if len(promoted) != args.expected_promoted_pass:
        parser.error(f"expected {args.expected_promoted_pass} promoted PASS candidates; found {len(promoted)}")
    immutable = [row for row in bridge.read_jsonl(bridge.COMPARISON_POOL) if row.get("validation_status") == "pass"]
    if len(immutable) != 133:
        parser.error(f"expected 133 immutable PASS candidates; found {len(immutable)}")
    current_pool = [*immutable, *promoted.values()]
    preflight = approved_preflight(
        approved_rows,
        bridge.read_jsonl(bridge.SEMANTIC_REQUESTS),
        [row["question"] for row in current_pool],
    )
    dedup = full_set_dedup(approved_rows, current_pool)
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    smoke_allowed = not preflight["failures"] and collision_count == 0
    audit = {
        "stage": "P49-2H-4D-D Linguistic Anchor Pilot — Human Approval",
        "external_hcx_calls": 0,
        "source_draft": str(args.input),
        "source_draft_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "source_draft_modified": False,
        "current_accepted_quality_pool": len(current_pool),
        "anchor_count": len(approved_rows),
        "anchor_count_by_cell": {
            cell: sum(row["coverage_cell"] == cell for row in approved_rows) for cell in v6.TARGET_CELLS
        },
        "authoring_status": "human_written",
        "human_review_status": "human_approved",
        "approval_provenance": "explicit_user_approval",
        "preflight": preflight,
        "anchor_full_set_dedup": dedup,
        "anchor_full_set_dedup_pass": collision_count == 0,
        "anchor_hcx_execution_allowed": smoke_allowed,
        "anchor_smoke_execution_allowed": smoke_allowed,
        "batch_07_execution_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    pilot.write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in approved_rows))
    pilot.write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "external_hcx_calls": 0,
                "anchor_count": len(approved_rows),
                "preflight_pass": preflight["preservation_prompt_and_semantic_pass"],
                "dedup_pass": audit["anchor_full_set_dedup_pass"],
                "anchor_smoke_execution_allowed": smoke_allowed,
                "output": str(args.output),
                "audit_output": str(args.audit_output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
