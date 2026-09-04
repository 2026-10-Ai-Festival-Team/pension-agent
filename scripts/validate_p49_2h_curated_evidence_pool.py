"""Evidence-first integrity validator for the P49-2H curated evidence pool."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
MATRIX = ROOT / "evaluation/fine_tuning/p49_2h_augmentation_coverage_matrix_v1.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(record: dict, corpus: dict[str, dict]) -> list[str]:
    required = {"pool_id", "domain", "canonical_requirement", "allowed_outcomes", "evidence_role", "source_id", "chunk_id", "evidence_text", "evidence_type", "numeric_anchors", "required_evidence_anchors", "table_fields", "optional_calculation_contract", "exclusion_constraints", "notes"}
    missing = sorted(required - record.keys())
    if missing:
        return [f"missing_fields:{','.join(missing)}"]
    chunk = corpus.get(record["chunk_id"])
    if chunk is None or record["chunk_id"].startswith("CHK-"):
        return ["opaque_or_missing_chunk_id"]
    findings: list[str] = []
    if record["source_id"] != chunk["source_id"]:
        findings.append("source_id_mismatch")
    if record["evidence_text"] != chunk["text"]:
        findings.append("evidence_text_not_exact_corpus_copy")
    expected_type = "table" if chunk["chunk_type"] == "table" else "paragraph"
    if record["evidence_type"] != expected_type:
        findings.append("evidence_type_mismatch")
    for anchor in [*record["numeric_anchors"], *record["required_evidence_anchors"], *record["table_fields"]]:
        if anchor not in chunk["text"]:
            findings.append("declared_anchor_missing_from_evidence")
            break
    if record["evidence_role"] == "optional_context_only" and record["allowed_outcomes"] != ["bounded_answer"]:
        findings.append("optional_context_outcome_contract_mismatch")
    if record["evidence_role"] == "direct_requirement_evidence" and "supported_answer" not in record["allowed_outcomes"]:
        findings.append("direct_evidence_missing_supported_outcome")
    if record["evidence_type"] != "table" and record["table_fields"]:
        findings.append("paragraph_must_not_declare_table_fields")
    return sorted(set(findings))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_v1.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_audit_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_audit_manifest_v1.json")
    args = parser.parse_args()
    corpus = {item["chunk_id"]: item for item in read_jsonl(CORPUS)}
    records = read_jsonl(args.input)
    audit = []
    for record in records:
        findings = validate(record, corpus)
        audit.append({"pool_id": record.get("pool_id"), "domain": record.get("domain"), "canonical_requirement": record.get("canonical_requirement"), "chunk_id": record.get("chunk_id"), "status": "PASS" if not findings else "FAIL", "findings": findings})
    domain_counts = Counter(record["domain"] for record in records)
    target_domains = {item["code"] for item in json.loads(MATRIX.read_text(encoding="utf-8"))["domain_targets"]}
    manifest = {"stage": "P49-2H-3A Curated Evidence Pool Audit", "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(), "record_count": len(records), "pass_count": sum(item["status"] == "PASS" for item in audit), "fail_count": sum(item["status"] == "FAIL" for item in audit), "opaque_chunk_id_count": sum(record.get("chunk_id", "").startswith("CHK-") for record in records), "covered_active_domains": sorted(domain_counts), "coverage_gaps": sorted(target_domains - set(domain_counts)), "candidate_generation_started": False, "training_export_allowed": False, "tuning_allowed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in audit), encoding="utf-8")
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))
    if manifest["fail_count"] or manifest["coverage_gaps"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
