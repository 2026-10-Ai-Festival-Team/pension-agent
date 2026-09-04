"""Re-audit the provenance-resolved P49-2H Robustness Remediation Seed v1."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
DEFAULT_SEED = ROOT / "evaluation/robustness/p49_2h_robustness_remediation_seed_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/robustness/p49_2h_robustness_remediation_reaudit_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "evaluation/robustness/p49_2h_robustness_remediation_reaudit_manifest_v1.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_status(requirements: list[dict], outcome: str) -> str:
    factual = [item for item in requirements if item["requirement_kind"] == "factual" and item["coverage_required"]]
    if not factual:
        return "unresolved" if outcome == "clarification_required" else "none"
    support = {item["support_status"] for item in factual}
    if support == {"supported"}:
        return "full"
    if support == {"unsupported"}:
        return "none"
    return "partial"


def audit_record(record: dict, corpus: dict[str, dict]) -> dict:
    requirements = record["requirements"]
    all_actual_ids = [chunk_id for item in requirements for chunk_id in item["evidence_chunk_ids"]]
    opaque_ids = [chunk_id for chunk_id in all_actual_ids if chunk_id.startswith("CHK-")]
    missing_ids = [chunk_id for chunk_id in all_actual_ids if chunk_id not in corpus]
    unsupported_with_evidence = [
        item["requirement"]
        for item in requirements
        if item["support_status"] == "unsupported" and item["evidence_chunk_ids"]
    ]
    required_unsupported_facts = [
        item["requirement"]
        for item in requirements
        if item["requirement_kind"] == "factual"
        and item["coverage_required"]
        and item["support_status"] == "supported"
        and not item.get("required_gold_facts")
    ]
    directness_failures = []
    for item in requirements:
        if item["support_status"] != "supported":
            continue
        evidence = item.get("evidence", [])
        if not evidence or [entry["chunk_id"] for entry in evidence] != item["evidence_chunk_ids"]:
            directness_failures.append(item["requirement"])
            continue
        if any(entry["text"] != corpus[entry["chunk_id"]]["text"] for entry in evidence):
            directness_failures.append(item["requirement"])
    computed = expected_status(requirements, record["outcome"])
    outcome_consistent = (
        (record["outcome"] == "supported_answer" and computed == "full")
        or (record["outcome"] == "clarification_required" and computed == "unresolved")
        or (record["outcome"] == "bounded_answer" and computed in {"partial", "none"})
    )
    findings = {
        "opaque_chk_ids": opaque_ids,
        "missing_chunk_ids": missing_ids,
        "unsupported_requirement_with_evidence": unsupported_with_evidence,
        "supported_requirement_without_required_gold_facts": required_unsupported_facts,
        "requirement_evidence_directness_failures": directness_failures,
        "evidence_status_mismatch": computed != record["evidence_status"],
        "outcome_mismatch": not outcome_consistent,
    }
    return {
        "record_id": record["record_id"],
        "status": "PASS" if not any(findings.values()) else "FAIL",
        "computed_evidence_status": computed,
        "outcome": record["outcome"],
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--human-approved",
        action="store_true",
        help="Record an integrity re-audit of an already human-approved frozen seed.",
    )
    args = parser.parse_args()

    records = read_jsonl(args.seed)
    corpus = {row["chunk_id"]: row for row in read_jsonl(CORPUS)}
    if len(records) != 36 or len({row["record_id"] for row in records}) != 36:
        raise RuntimeError("Expected 36 distinct remediation seed records.")
    audited = [audit_record(record, corpus) for record in records]
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in audited), encoding="utf-8")
    totals = Counter(row["status"] for row in audited)
    finding_counts = Counter(
        key for row in audited for key, value in row["findings"].items() if value
    )
    passed = totals == {"PASS": 36}
    manifest = {
        "stage": "P49-2H Robustness Remediation Seed v1 Re-Audit",
        "seed_sha256": hashlib.sha256(args.seed.read_bytes()).hexdigest(),
        "record_count": len(records),
        "pass_count": totals["PASS"],
        "fail_count": totals["FAIL"],
        "finding_counts": dict(finding_counts),
        "gate": {
            "CHK_remaining": 0,
            "actual_chunk_id_exists": "36/36",
            "requirement_evidence_directness": "PASS",
            "unsupported_requirement_with_evidence": 0,
            "supported_requirement_without_required_gold_facts": 0,
            "evidence_status_match": "36/36",
            "outcome_match": "36/36",
        },
        "result": (
            "FROZEN_INTEGRITY_PASS"
            if passed and args.human_approved
            else "GO_FOR_HUMAN_REVIEW"
            if passed
            else "NO_GO"
        ),
        "training_export_allowed": False,
        "freeze_allowed": False if not args.human_approved else "completed",
        "next_required_action": (
            "P49-2H domain-grounded augmentation and its evidence-first QA."
            if passed and args.human_approved
            else "Human review and approval only if result is GO_FOR_HUMAN_REVIEW."
        ),
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
