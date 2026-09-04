"""Freeze the user-approved P49 v6 review candidate without rewriting it."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
GOLD = BASE / "p49_human_review_candidate_gold_v6.jsonl"
CONTRASTIVE = BASE / "p49_human_review_candidate_contrastive_v6.jsonl"
AUDIT = BASE / "p49_team_merge_review_candidate_v6_audit.jsonl"
AUDIT_MANIFEST = BASE / "p49_team_merge_review_candidate_v6_audit_manifest.json"
OUT_DATASET = BASE / "p49_gold_seed_records_v2.jsonl"
OUT_LEDGER = BASE / "p49_human_review_ledger_v6_final.jsonl"
OUT_MANIFEST = BASE / "p49_gold_seed_manifest_v2.json"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = [*load(GOLD), *load(CONTRASTIVE)]
    audit = load(AUDIT)
    audit_manifest = json.loads(AUDIT_MANIFEST.read_text(encoding="utf-8"))
    if len(records) != 38 or len({record["record_id"] for record in records}) != 38:
        raise RuntimeError("P49 Gold Seed v2 requires exactly 38 distinct records")
    if len(audit) != 38 or any(row["audit_status"] != "PASS" for row in audit):
        raise RuntimeError("P49 Gold Seed v2 requires an evidence-first 38/38 PASS audit")
    if audit_manifest.get("training_export_allowed") is not False:
        raise RuntimeError("unexpected audit manifest training-export state")

    approved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    frozen_records = []
    review_ledger = []
    for record in records:
        frozen_records.append({
            **record,
            "quality": {
                **record["quality"],
                "manual_review": "approved_p49_gold_seed_v2",
            },
        })
        review_ledger.append({
            "record_id": record["record_id"],
            "review_status": "approved",
            "reviewer": "project_owner",
            "reviewed_at": approved_at,
            "reviewer_note": "Approved after P49-2G6 evidence-first re-audit and v6 team-merge review.",
            "review_criteria": [
                "question_requirement_alignment",
                "required_fact_completeness",
                "direct_evidence_grounding",
                "adjacent_field_precision",
                "answer_format_quality",
            ],
        })
    write(OUT_DATASET, frozen_records)
    write(OUT_LEDGER, review_ledger)
    manifest = {
        "dataset_status": "frozen_gold_seed_v2",
        "record_count": len(frozen_records),
        "human_approved": len(review_ledger),
        "human_pending": 0,
        "reviewer": "project_owner",
        "approved_at": approved_at,
        "outcome_distribution": {"supported_answer": len(frozen_records)},
        "evidence_status_distribution": {"full": len(frozen_records)},
        "required_fact_coverage": "38/38",
        "evidence_grounding": "38/38",
        "citation_context_match": "38/38",
        "wrong_field_claims": 0,
        "source_candidates": {GOLD.name: sha256(GOLD), CONTRASTIVE.name: sha256(CONTRASTIVE)},
        "evidence_first_audit": {AUDIT.name: sha256(AUDIT), AUDIT_MANIFEST.name: sha256(AUDIT_MANIFEST)},
        "canonical_dataset_sha256": sha256(OUT_DATASET),
        "human_review_ledger_sha256": sha256(OUT_LEDGER),
        "supersedes": "p49_gold_seed_records_v1.jsonl",
        "tuning_api_calls": 0,
        "ncp_resource_changes": 0,
        "next_allowed_stage": "P49-2H domain-grounded augmentation design",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(frozen_records), "dataset_sha256": manifest["canonical_dataset_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
