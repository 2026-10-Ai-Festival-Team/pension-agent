"""Build the P49-2H Robustness Remediation Seed v1 from its audit artifact.

The source CSV is intentionally not modified.  The generated seed is a
requirement-level, provenance-resolved candidate for human review; it is not a
training export and may not be used for tuning until its companion re-audit
passes and a human freezes it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/robustness/p49_2h_robustness_provenance_audit_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/robustness/p49_2h_robustness_remediation_seed_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "evaluation/robustness/p49_2h_robustness_remediation_seed_manifest_v1.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evidence_items(chunk_ids: list[str], corpus: dict[str, dict]) -> list[dict]:
    return [
        {
            "chunk_id": chunk_id,
            "source_path": corpus[chunk_id]["source_path"],
            "locator": corpus[chunk_id]["locator"],
            "chunk_type": corpus[chunk_id]["chunk_type"],
            "text": corpus[chunk_id]["text"],
        }
        for chunk_id in chunk_ids
    ]


def normalize_requirement(requirement: dict, corpus: dict[str, dict]) -> dict:
    item = {
        "requirement": requirement["requirement"],
        "requirement_kind": requirement["requirement_kind"],
        "coverage_required": requirement["coverage_required"],
        "support_status": requirement["support_status"],
        "evidence_chunk_ids": requirement["evidence_chunk_ids"],
        "evidence": evidence_items(requirement["evidence_chunk_ids"], corpus),
    }
    if requirement["requirement_kind"] == "factual" and requirement["support_status"] == "supported":
        item["required_gold_facts"] = requirement["independent_gold_facts"]
    elif requirement["requirement_kind"] == "optional_relevant_context":
        item["optional_relevant_context"] = requirement["independent_gold_facts"]
    elif requirement["requirement_kind"] == "factual" and requirement["support_status"] == "unsupported":
        # This is an answer-boundary instruction, not an evidence-grounded
        # factual claim.  Keeping it separate prevents unsupported facts from
        # leaking into required gold-fact coverage.
        item["bounded_answer_instruction"] = requirement["independent_gold_facts"]
    else:
        item["policy_instruction"] = requirement["independent_gold_facts"]
    return item


def build_seed(audit_rows: list[dict], corpus: dict[str, dict]) -> list[dict]:
    seeds: list[dict] = []
    for row in audit_rows:
        if row["audit_status"] != "REMEDIATION_REQUIRED":
            raise RuntimeError(f"Unexpected audit state for {row['record_id']}: {row['audit_status']}")
        requirements = [normalize_requirement(item, corpus) for item in row["requirements"]]
        required_gold_facts = [
            fact
            for item in requirements
            for fact in item.get("required_gold_facts", [])
        ]
        optional_context = [
            {
                "requirement": item["requirement"],
                "facts": item["optional_relevant_context"],
                "evidence_chunk_ids": item["evidence_chunk_ids"],
            }
            for item in requirements
            if "optional_relevant_context" in item
        ]
        seeds.append(
            {
                "record_id": row["record_id"],
                "question": row["question"],
                "outcome": row["outcome"],
                "evidence_status": row["computed_evidence_status"],
                "requirements": requirements,
                "required_gold_facts": required_gold_facts,
                "optional_relevant_context": optional_context,
                "open_close": row["open_close"],
                "outcome_is_authoritative": True,
                "source_of_truth": "p49_2h_robustness_provenance_audit_v1",
                "export_status": "human_review_pending",
            }
        )
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    audit_rows = read_jsonl(args.audit)
    corpus = {row["chunk_id"]: row for row in read_jsonl(CORPUS)}
    if len(audit_rows) != 36 or len({row["record_id"] for row in audit_rows}) != 36:
        raise RuntimeError("Expected 36 distinct robustness audit rows.")
    seeds = build_seed(audit_rows, corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in seeds), encoding="utf-8")
    manifest = {
        "stage": "P49-2H Robustness Remediation Seed v1",
        "record_count": len(seeds),
        "audit_input": str(args.audit.relative_to(ROOT)),
        "audit_sha256": hashlib.sha256(args.audit.read_bytes()).hexdigest(),
        "seed_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "source_csv_is_unchanged": True,
        "training_export_allowed": False,
        "freeze_allowed": False,
        "next_required_action": "Run P49-2H robustness remediation re-audit, then conduct human approval before any freeze or export.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
