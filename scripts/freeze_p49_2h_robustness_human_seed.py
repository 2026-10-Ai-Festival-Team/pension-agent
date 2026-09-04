"""Freeze the human-approved P49-2H Robustness Human Seed v1.

This script promotes only a seed whose re-audit result is
``GO_FOR_HUMAN_REVIEW``.  The promoted artifact remains unsuitable for direct
tuning export: it is an approved human seed for the later augmentation stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/robustness"
DEFAULT_SEED = BASE / "p49_2h_robustness_remediation_seed_v1.jsonl"
DEFAULT_REAUDIT = BASE / "p49_2h_robustness_remediation_reaudit_manifest_v1.json"
DEFAULT_OUTPUT = BASE / "p49_2h_robustness_human_seed_v1.jsonl"
DEFAULT_LEDGER = BASE / "p49_2h_robustness_human_review_ledger_v1.jsonl"
DEFAULT_MANIFEST = BASE / "p49_2h_robustness_human_seed_manifest_v1.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--reaudit", type=Path, default=DEFAULT_REAUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--reviewer", default="jun")
    args = parser.parse_args()

    reaudit = json.loads(args.reaudit.read_text(encoding="utf-8"))
    seed_sha = sha256(args.seed)
    if reaudit.get("result") != "GO_FOR_HUMAN_REVIEW":
        raise RuntimeError("The remediation re-audit has not passed human-review gating.")
    if reaudit.get("seed_sha256") != seed_sha:
        raise RuntimeError("The remediation seed differs from the re-audited seed.")

    records = read_jsonl(args.seed)
    if len(records) != 36 or len({record["record_id"] for record in records}) != 36:
        raise RuntimeError("Expected exactly 36 distinct remediation records.")
    approved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ledger: list[dict] = []
    frozen: list[dict] = []
    for record in records:
        review = {
            "status": "approved",
            "reviewer": args.reviewer,
            "approved_at": approved_at,
            "note": "User approved the 36-record robustness seed after provenance re-audit.",
        }
        ledger.append({"record_id": record["record_id"], **review})
        frozen.append({**record, "human_review": review, "export_status": "frozen_human_seed"})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in frozen), encoding="utf-8")
    args.ledger.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ledger), encoding="utf-8")
    manifest = {
        "stage": "P49-2H Robustness Human Seed v1",
        "status": "FROZEN_GO",
        "record_count": len(frozen),
        "human_approved": f"{len(frozen)}/{len(frozen)}",
        "reviewer": args.reviewer,
        "approval_timestamp": approved_at,
        "remediation_seed_sha256": seed_sha,
        "reaudit_manifest_sha256": sha256(args.reaudit),
        "frozen_seed_sha256": sha256(args.output),
        "review_ledger_sha256": sha256(args.ledger),
        "augmentation_input_allowed": True,
        "training_export_allowed": False,
        "tuning_allowed": False,
        "next_allowed_stage": "P49-2H domain-grounded augmentation and its evidence-first QA.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
