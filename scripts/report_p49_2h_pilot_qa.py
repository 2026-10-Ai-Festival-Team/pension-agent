"""Summarize a validated P49-2H-3B pilot without changing any candidate state."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def family(findings: list[str]) -> str:
    text = " ".join(findings)
    if "missing_" in text or "malformed" in text:
        return "schema_or_required_field"
    if "evidence" in text or "anchor" in text or "numeric" in text:
        return "evidence_or_numeric"
    if "outcome" in text or "status" in text or "support" in text:
        return "outcome_or_behavior_policy"
    if "duplicate" in text or "seed" in text:
        return "duplicate_or_seed_leakage"
    return "other_validator"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.validated)
    failures = [row for row in rows if row.get("validation_status") == "fail"]
    family_counts = Counter(family(row.get("validation_findings", [])) for row in failures)
    by_outcome = {outcome: {"total": sum(row.get("outcome") == outcome for row in rows), "failed": sum(row.get("outcome") == outcome and row.get("validation_status") == "fail" for row in rows)} for outcome in ("supported_answer", "clarification_required", "bounded_answer")}
    # A deterministic spot-review list; human reviewers decide false positives
    # and false negatives. The report does not manufacture those labels.
    review_ids = [row.get("candidate_id") for row in rows[::7]][:12]
    report = {
        "stage": "P49-2H-3B Pilot QA Report", "validated_input_sha256": hashlib.sha256(args.validated.read_bytes()).hexdigest(),
        "record_count": len(rows), "validation_pass_count": len(rows) - len(failures), "validation_fail_count": len(failures),
        "validation_failure_rate": len(failures) / len(rows) if rows else None,
        "failure_family_counts": dict(family_counts), "lane_failure_counts": by_outcome,
        "human_spot_review_candidate_ids": review_ids,
        "human_review_questions": ["schema/validator false positive?", "validator false negative?", "evidence outside claim?", "numeric/period/fee field confusion?", "outcome drift?", "polarity or exclusion-scope error?", "near-copy or frozen-seed leakage?"],
        "accepted_records": 0, "training_export_allowed": False, "tuning_allowed": False,
        "next_required_action": "Evidence-first human spot review and failure attribution; do not promote pilot records automatically.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
