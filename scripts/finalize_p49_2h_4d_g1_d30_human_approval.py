"""Record the user-supplied D30 rewrites as a separate approved G1 artifact.

The G1 draft JSONL is immutable and remains labelled ``drafted_by_codex``.
Only its four D30 rows are replaced with text supplied/reviewed by the user in
this conversation; the four already-approved reused anchors are copied as-is.
No HCX call is made here.
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

from scripts import build_p49_2h_4d_g1_bounded_anchor_inventory as g1
from scripts import run_p49_2h_4c_execution_bridge as bridge


DEFAULT_INPUT = g1.DEFAULT_SMOKE_DRAFTS
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_human_approved_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_human_approved_audit_v1.json"
HUMAN_REWRITES = {
    "P49-2H-4D-G1-D30-DRAFT-0001": "이 상품을 계속 가져갈지 계획 중인데, 앞으로 위험등급이 몇 등급이 될지 지금 자료만으로 알 수 있어?",
    "P49-2H-4D-G1-D30-DRAFT-0002": "해당 상품의 위험등급이 앞으로 어느 등급이 될지, 또는 언제 바뀔지까지 이미 정해져 있는 거야?",
    "P49-2H-4D-G1-D30-DRAFT-0003": "이 상품은 지금 나온 자료만으로 미래 위험등급의 구체적인 등급이나 변경 시점까지 확인할 수 있는 건 아니지?",
    "P49-2H-4D-G1-D30-DRAFT-0004": "해당 상품의 현재 안내를 보면 앞으로 위험등급도 비슷하게 유지될 거라고 생각했는데, 그렇게 단정할 수는 없는 거지?",
}


def approve_rows(draft_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply exactly the reviewed D30 wording, preserving draft source rows."""
    if len(draft_rows) != 8:
        raise ValueError(f"expected exactly eight G1 smoke rows; found {len(draft_rows)}")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in draft_rows:
        row = deepcopy(draft)
        request_id = row.get("remediation_request_id")
        if not isinstance(request_id, str) or request_id in seen:
            raise ValueError(f"invalid or duplicate G1 request ID: {request_id!r}")
        seen.add(request_id)
        anchor = row.get("bounded_linguistic_anchor")
        if not isinstance(anchor, dict):
            raise ValueError(f"missing bounded linguistic anchor: {request_id}")
        if request_id in HUMAN_REWRITES:
            if anchor.get("authoring_status") != "drafted_by_codex" or anchor.get("human_review_status") != "human_review_required":
                raise ValueError(f"D30 review source is not a pending draft: {request_id}")
            anchor["draft_anchor_question"] = anchor["anchor_question"]
            anchor["anchor_question"] = HUMAN_REWRITES[request_id]
            anchor["authoring_status"] = "human_written"
            anchor["human_review_status"] = "human_approved"
            anchor["approval_provenance"] = "user_supplied_rewrite_and_explicit_approval"
            row["g1_anchor_kind"] = "human_written_d30_anchor"
            row["g1_smoke_status"] = "approved_for_g2_smoke"
        elif (
            anchor.get("authoring_status") != "human_written"
            or anchor.get("human_review_status") != "human_approved"
        ):
            raise ValueError(f"non-D30 G1 row must already be human approved: {request_id}")
        output.append(row)
    if set(HUMAN_REWRITES) != seen & set(HUMAN_REWRITES):
        raise ValueError("approved G1 input does not contain exactly the expected four D30 drafts")
    return output


def approved_preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    """Reuse the G1 local checks, then expose the all-approved execution gate."""
    report = g1.preflight(rows, semantic_rows, pool)
    approved = report["human_written_human_approved"] == len(rows)
    return {
        **report,
        "human_written_human_approved": sum(
            row["bounded_linguistic_anchor"]["authoring_status"] == "human_written"
            and row["bounded_linguistic_anchor"]["human_review_status"] == "human_approved"
            for row in rows
        ),
        "g2_hcx_execution_allowed": approved and not report["failures"] and report["full_529_pool_dedup_pass"],
        "g2_hcx_block_reason": None if approved and not report["failures"] and report["full_529_pool_dedup_pass"] else "approval, preflight, or full-set dedup gate failed",
    }


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite G1 approval artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--comparison-pool", type=Path, default=g1.COMPARISON_POOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    draft_rows = bridge.read_jsonl(args.input)
    pool = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(pool) != 529:
        parser.error(f"expected frozen 529-PASS pool; found {len(pool)}")
    approved_rows = approve_rows(draft_rows)
    report = approved_preflight(approved_rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    audit = {
        "stage": "P49-2H-4D-G1 D30 Human Rewrite / Approval",
        "external_hcx_calls": 0,
        "source_draft": str(args.input),
        "source_draft_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "source_draft_modified": False,
        "comparison_pool_count": len(pool),
        "d30_user_rewrite_count": len(HUMAN_REWRITES),
        "approval_provenance": "user_supplied_rewrite_and_explicit_approval",
        "preflight": report,
        "g2_hcx_execution_allowed": report["g2_hcx_execution_allowed"],
        "batch_08_original_manifest_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in approved_rows))
    write_new(args.audit_output, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "records": len(approved_rows),
        "human_written_human_approved": report["human_written_human_approved"],
        "preflight_pass": report["preservation_prompt_and_semantic_pass"],
        "dedup_pass": report["full_529_pool_dedup_pass"],
        "g2_hcx_execution_allowed": report["g2_hcx_execution_allowed"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
