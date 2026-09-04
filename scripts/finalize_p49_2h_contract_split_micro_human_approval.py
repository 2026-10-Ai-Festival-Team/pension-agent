"""Freeze the user-authorized human approval for P49-2H-3D v4.

This promotes only the review ledger.  It does not accept training candidates,
export data, or invoke HCX.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_human_review_ledger_v4_remediation_r1.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_human_review_approved_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_human_review_approved_manifest_v1.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--reviewer", default="project_owner")
    args = parser.parse_args()

    rows = read_jsonl(args.input)
    if len(rows) != 35:
        raise RuntimeError("P49-2H-3D approval requires exactly 35 final review rows.")
    if any(row["review_status"] != "pending_human" for row in rows):
        raise RuntimeError("Input ledger is not a clean pending-human review set.")
    if any(row["assistant_evidence_first_precheck"] != "pass_recommended" for row in rows):
        raise RuntimeError("Cannot finalize approval while an assistant evidence-first blocker remains.")
    if any(row["acceptance_status"] != "not_accepted" for row in rows):
        raise RuntimeError("Human review approval must not begin from an accepted candidate state.")

    approved_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    approved = []
    for row in rows:
        approved.append({
            **row,
            "review_status": "human_reviewed",
            "human_decision": "pass",
            "reviewer": args.reviewer,
            "reviewed_at": approved_at,
            "reviewer_note": "User-authorized final approval after evidence-first review.",
            # Review approval is intentionally distinct from accepted-training
            # status; raw 700, selection, and export gates remain separate.
            "acceptance_status": "not_accepted",
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in approved), encoding="utf-8")
    manifest = {
        "stage": "P49-2H-3D Final Human Evidence-First Approval",
        "status": "final_go",
        "approved_records": len(approved),
        "reviewer": args.reviewer,
        "approved_at": approved_at,
        "input_ledger_sha256": sha256(args.input),
        "approved_ledger_sha256": sha256(args.output),
        "accepted_records": 0,
        "full_raw_700_generation_allowed": True,
        "training_export_allowed": False,
        "tuning_allowed": False,
        "next_required_action": "Generate the oversampled raw 700 candidate pool; validate and review before acceptance/export.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
