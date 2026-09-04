"""Build an auditable bridge from question-bank DOC IDs to corpus sources.

Only records with an independently verifiable source identity are promoted to
``verified``.  The remaining DOC IDs are retained as explicit unresolved
records so evaluation never mistakes an ID-namespace gap for retrieval
failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# These three links are independently verifiable from a single-product JSON
# question and the canonical product title/code on the corresponding original
# prospectus.  Do not promote other links from lexical similarity alone.
VERIFIED_PRODUCT_DOCUMENTS = {
    "DOC-7FB4C074DD06": "KR510902511M",
    "DOC-34D1B016008A": "KR5110501016",
    "DOC-61711D13FCFE": "KR5111420047",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=ROOT / "evaluation/closed_core_benchmark_v1.jsonl")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/provenance/document_id_bridge_v1.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/document_id_provenance_bridge_v1.md")
    args = parser.parse_args()

    document_ids = sorted({
        item["document_id"]
        for record in _jsonl(args.benchmark)
        for item in record["fixtures"]["retrieval"].get("required_evidence", ())
    })
    corpus = _jsonl(args.corpus)
    records = []
    for document_id in document_ids:
        code = VERIFIED_PRODUCT_DOCUMENTS.get(document_id)
        source_matches = {
            (chunk["source_id"], chunk["source_path"])
            for chunk in corpus
            if code and code in {item.upper() for item in chunk.get("product_codes", ())}
        }
        if len(source_matches) == 1:
            source_id, source_path = source_matches.pop()
            records.append({
                "document_id": document_id,
                "mapping_status": "verified",
                "corpus_source_ids": [source_id],
                "corpus_source_paths": [source_path],
                "verification_basis": "single-product question-bank evidence plus canonical name/code in original prospectus",
            })
        else:
            records.append({
                "document_id": document_id,
                "mapping_status": "unresolved",
                "corpus_source_ids": [],
                "corpus_source_paths": [],
                "verification_basis": "no trusted DOC-ID namespace mapping supplied by corpus metadata",
            })
    verified = sum(record["mapping_status"] == "verified" for record in records)
    payload = {
        "schema_version": "1.0",
        "purpose": "Evaluation provenance only; this bridge is not read by runtime retrieval.",
        "records": records,
        "summary": {"total": len(records), "verified": verified, "unresolved": len(records) - verified},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text("\n".join((
        "# DOC-ID to Corpus Provenance Bridge v1",
        "",
        "## Result",
        "",
        f"- Question-bank DOC IDs: **{len(records)}**",
        f"- Verified corpus mappings: **{verified}**",
        f"- Explicitly unresolved mappings: **{len(records) - verified}**",
        "",
        "## Contract",
        "",
        "- This table is evaluation provenance only and is deliberately separate from retrieval logic.",
        "- An unresolved DOC ID is not a retrieval failure and cannot count as a source-recall pass.",
        "- Only original-source identity evidence may promote an unresolved record to `verified`; same-topic text or same-document guesses are insufficient.",
        "",
    )), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
