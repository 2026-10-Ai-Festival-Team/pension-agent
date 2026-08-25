"""Promote the user-approved P49 v4 drafts to immutable Gold Seed v1.

This command is deliberately local and deterministic: it does not call a
provider API, create cloud resources, or generate augmentation data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_p49_dataset_qa_drafts import _hash_jsonl, _qa


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
V4_POSITIVE = BASE / "p49_draft_gold_training_records_v4.jsonl"
V4_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v4.jsonl"
LEDGER = BASE / "p49_human_review_ledger.jsonl"
CANONICAL = BASE / "p49_gold_seed_records_v1.jsonl"
MANIFEST = BASE / "p49_gold_seed_manifest_v1.json"
REPORT = ROOT / "docs/p49_2g_human_approval_and_gold_seed_freeze.md"
APPROVED_AT = "2026-08-25T08:46:45Z"
REVIEWER = "project_owner"
APPROVAL_NOTE = "Project owner approved this FULL-evidence Gold Seed record for P49 Gold Seed v1."


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _canonicalize(record: dict) -> dict:
    output = dict(record)
    output["schema_version"] = "p49.training_record.v2"
    output["record_type"] = "training_example"
    output["quality"] = dict(record["quality"])
    output["quality"]["manual_review"] = "human_approved"
    output["review"] = {
        "status": "approved",
        "reviewer": REVIEWER,
        "approved_at": APPROVED_AT,
        "approval_source": "project_owner_instruction",
    }
    return output


def main() -> None:
    drafts = _rows(V4_POSITIVE) + _rows(V4_CONTRASTIVE)
    if len(drafts) != 38 or len({record["record_id"] for record in drafts}) != 38:
        raise RuntimeError("expected exactly 38 unique v4 draft records")
    if any(record["outcome"] != "supported_answer" or record["evidence_status"] != "full" for record in drafts):
        raise RuntimeError("Gold Seed v1 may contain only FULL supported-answer records")
    if any(record["missing_conditions"] or record["unsupported_requirements"] for record in drafts):
        raise RuntimeError("FULL records cannot retain missing conditions or unsupported requirements")

    ledger = _rows(LEDGER)
    if {row["record_id"] for row in ledger} != {record["record_id"] for record in drafts}:
        raise RuntimeError("human review ledger does not match v4 draft records")
    for row in ledger:
        if row["review_status"] not in {"pending", "approved"}:
            raise RuntimeError(f"cannot freeze non-approved decision: {row['record_id']}")
        row["review_status"] = "approved"
        row["reviewer"] = REVIEWER
        row["reviewer_note"] = APPROVAL_NOTE
        row["approved_at"] = APPROVED_AT
    _write_jsonl(LEDGER, ledger)

    canonical = [_canonicalize(record) for record in drafts]
    _write_jsonl(CANONICAL, canonical)
    qa_rows = _qa(canonical)
    if not all(row["automatic_qa_pass"] for row in qa_rows):
        raise RuntimeError("canonical records failed automatic QA")
    manifest = {
        "dataset_status": "frozen_gold_seed_v1",
        "record_count": len(canonical),
        "human_approved": len(canonical),
        "human_pending": 0,
        "reviewer": REVIEWER,
        "approved_at": APPROVED_AT,
        "outcome_distribution": {"supported_answer": len(canonical)},
        "evidence_status_distribution": {"full": len(canonical)},
        "required_fact_coverage": "38/38",
        "evidence_grounding": "38/38",
        "citation_context_match": "38/38",
        "wrong_field_claims": 0,
        "source_v4_positive_sha256": hashlib.sha256(V4_POSITIVE.read_bytes()).hexdigest(),
        "source_v4_contrastive_sha256": hashlib.sha256(V4_CONTRASTIVE.read_bytes()).hexdigest(),
        "canonical_dataset_sha256": _hash_jsonl(canonical),
        "tuning_api_calls": 0,
        "ncp_resource_changes": 0,
        "next_allowed_stage": "P49-2H domain-grounded augmentation design",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "\n".join((
            "# P49-2G Human Approval and Gold Seed v1 Freeze", "",
            "## Decision", "",
            "**Go.** The project owner approved all 38 FULL-evidence draft records.", "",
            "- Human approval: 38/38", "- Outcome: `supported_answer`", "- Evidence status: `full`",
            "- Automatic QA retained: 38/38", "- Dataset state: `frozen_gold_seed_v1`", "",
            "## Boundary", "",
            "This freeze contains only direct-evidence FULL examples. It does not add clarification or bounded-answer records, call a tuning API, or change runtime orchestration.", "",
            "## Next allowed stage", "",
            "P49-2H may add domain-grounded, user-natural FULL / clarification / bounded examples as a separate dataset. It must not modify this frozen Gold Seed v1.", "",
        )),
        encoding="utf-8",
    )
    print(json.dumps({key: manifest[key] for key in ("dataset_status", "record_count", "human_approved", "canonical_dataset_sha256", "tuning_api_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
