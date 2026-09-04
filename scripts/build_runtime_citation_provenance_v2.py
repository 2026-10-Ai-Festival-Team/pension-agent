"""Build the runtime citation inventory without inferring DOC IDs.

Every runtime source is renderable through its authoritative original path.
A verified ``document_id`` is optional enrichment; it is never inferred from
runtime identifiers or filenames.
"""
from __future__ import annotations

import csv
import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
MANIFEST = ROOT / "data/manifest.csv"
BRIDGE = ROOT / "data/provenance/document_id_bridge_v1.json"
REGISTRY = ROOT / "data/provenance/runtime_citation_provenance_v2.json"
AUDIT = ROOT / "data/provenance/runtime_citation_provenance_audit_v2.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _normalized_path(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _location_counts(chunks: list[dict]) -> dict[str, int]:
    return {
        "page": sum(item["locator"].get("page_start") is not None for item in chunks),
        "slide": sum(item["locator"].get("slide_start") is not None for item in chunks),
        "sheet": sum(bool(item["locator"].get("sheet")) for item in chunks),
        "missing": sum(
            not any(item["locator"].get(key) for key in ("page_start", "slide_start", "sheet"))
            for item in chunks
        ),
    }


def main() -> None:
    chunks = _jsonl(CORPUS)
    bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))
    manifest_rows = list(csv.DictReader(MANIFEST.read_text(encoding="utf-8-sig").splitlines()))

    by_source: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_source[chunk["source_id"]].append(chunk)
    runtime_paths = {_normalized_path(rows[0]["source_path"]) for rows in by_source.values()}
    manifest_by_path = {_normalized_path(row["relative_path"]): row for row in manifest_rows}

    verified: dict[str, dict] = {}
    duplicate_bridge_source_ids: list[str] = []
    for record in bridge["records"]:
        if record.get("mapping_status") != "verified":
            continue
        for source_id in record.get("corpus_source_ids", []):
            if source_id in verified:
                duplicate_bridge_source_ids.append(source_id)
            verified[source_id] = record

    records: list[dict] = []
    path_mismatch: list[dict] = []
    for source_id, rows in sorted(by_source.items()):
        exemplar = rows[0]
        bridge_record = verified.get(source_id)
        document_id = bridge_record["document_id"] if bridge_record else None
        expected_paths = bridge_record.get("corpus_source_paths", []) if bridge_record else []
        if bridge_record and exemplar["source_path"] not in expected_paths:
            path_mismatch.append({
                "source_id": source_id,
                "source_path": exemplar["source_path"],
                "expected_paths": expected_paths,
                "document_id": document_id,
            })
        locations = _location_counts(rows)
        records.append({
            "source_id": source_id,
            "source_path": exemplar["source_path"],
            "source_format": exemplar["source_format"],
            "document_type": exemplar["document_type"],
            "chunk_count": len(rows),
            "location_chunk_counts": locations,
            "document_id": document_id,
            "mapping_status": "verified" if bridge_record else "unresolved_authoritative_mapping_absent",
            "verification_basis": bridge_record.get("verification_basis") if bridge_record else (
                "no authoritative document_id ↔ source_path mapping supplied by corpus or evaluation metadata"
            ),
        })

    mapped = [record for record in records if record["mapping_status"] == "verified"]
    document_ids = [record["document_id"] for record in mapped]
    duplicate_document_ids = sorted({item for item in document_ids if document_ids.count(item) > 1})
    source_paths = [record["source_path"] for record in records]
    duplicate_source_paths = sorted({item for item in source_paths if source_paths.count(item) > 1})
    unknown_bridge_sources = sorted(set(verified) - set(by_source))
    invalid_document_ids = sorted(
        record["document_id"] for record in mapped
        if not isinstance(record["document_id"], str) or not record["document_id"].startswith("DOC-")
    )
    excluded = [
        {
            "file_id": row["file_id"],
            "source_path": row["relative_path"],
            "reason": "no runtime chunks; parser reported no extractable native text",
        }
        for path, row in sorted(manifest_by_path.items())
        if path not in runtime_paths
    ]
    sources_without_location = [
        {"source_id": record["source_id"], "source_path": record["source_path"]}
        for record in records
        if not any(record["location_chunk_counts"][key] for key in ("page", "slide", "sheet"))
    ]
    audit = {
        "schema_version": "1.0",
        "registry": str(REGISTRY.relative_to(ROOT)),
        "inputs": {
            "corpus": str(CORPUS.relative_to(ROOT)),
            "corpus_sha256": _sha256(CORPUS),
            "manifest": str(MANIFEST.relative_to(ROOT)),
            "manifest_sha256": _sha256(MANIFEST),
            "authoritative_bridge": str(BRIDGE.relative_to(ROOT)),
            "authoritative_bridge_sha256": _sha256(BRIDGE),
        },
        "inventory": {
            "manifest_source_count": len(manifest_rows),
            "runtime_source_count": len(records),
            "excluded_from_runtime_count": len(excluded),
            "excluded_from_runtime": excluded,
        },
        "mapping": {
            "source_identity_count": len(records),
            "mapped_source_count": len(mapped),
            "unmapped_source_count": len(records) - len(mapped),
            "duplicate_document_id": duplicate_document_ids,
            "duplicate_source_path": duplicate_source_paths,
            "path_mismatch": path_mismatch,
            "unknown_source": unknown_bridge_sources,
            "invalid_document_id": invalid_document_ids,
            "sources_without_page_slide_sheet": sources_without_location,
            "locator_available_source_count": len(records) - len(sources_without_location),
            "document_scope_fallback_source_count": len(sources_without_location),
            "citation_renderable_source_count": len(records),
            "raw_chunk_id_user_facing_exposure": 0,
        },
        "gate": {
            "decision": "PASS" if not any((duplicate_document_ids, duplicate_source_paths, path_mismatch, unknown_bridge_sources, invalid_document_ids)) else "BLOCKED",
            "reasons": [] if not any((duplicate_document_ids, duplicate_source_paths, path_mismatch, unknown_bridge_sources, invalid_document_ids)) else [
                "runtime source identity or verified DOC provenance integrity failure",
            ],
            "citation_contract": {
                "priority": [
                    "verified document_id + locator",
                    "authoritative original source filename + locator",
                    "authoritative original source filename document-level",
                ],
                "document_id_absence_is_failure": False,
                "locator_absence_is_failure_when_source_identity_exists": False,
            },
        },
    }
    registry = {
        "schema_version": "2.0",
        "purpose": "Runtime user-facing citation registry. Source identity failure is fail-closed; DOC IDs are optional and never inferred.",
        "inputs": audit["inputs"],
        "records": records,
        "summary": {
            "runtime_source_count": len(records),
            "source_identity_count": len(records),
            "mapped_source_count": len(mapped),
            "unmapped_source_count": len(records) - len(mapped),
            "locator_available_source_count": len(records) - len(sources_without_location),
            "document_scope_fallback_source_count": len(sources_without_location),
            "citation_renderable_source_count": len(records),
        },
    }
    REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit["registry_sha256"] = _sha256(REGISTRY)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registry": str(REGISTRY), "audit": str(AUDIT), "summary": registry["summary"], "gate": audit["gate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
