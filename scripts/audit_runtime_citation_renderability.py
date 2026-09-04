"""Audit that every runtime source can produce a safe user-facing citation.

This is intentionally host-only: it exercises the exact renderer used at
runtime without calling HCX or modifying retrieval, training, or prompts.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.citation_renderer import DocumentCitationRenderer


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
REGISTRY = ROOT / "data/provenance/runtime_citation_provenance_v2.json"
OUTPUT = ROOT / "data/provenance/runtime_citation_renderability_audit_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _representative_by_source() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        chunk = json.loads(line)
        source_id = chunk["source_id"]
        # Prefer a locator when a source has one, but retain a no-locator row
        # so document-level fallback is explicitly exercised for those sources.
        current = rows.get(source_id)
        locator = chunk["locator"]
        has_locator = any(locator.get(key) for key in ("page_start", "slide_start", "sheet"))
        if current is None or (has_locator and not any(current["locator"].get(key) for key in ("page_start", "slide_start", "sheet"))):
            rows[source_id] = chunk
    return rows


def _context(chunk: dict) -> SearchResult:
    locator = chunk["locator"]
    return SearchResult(
        rank=1,
        chunk_id=chunk["chunk_id"],
        score=1.0,
        text=chunk["text"],
        source_id=chunk["source_id"],
        source_path=chunk["source_path"],
        source_format=chunk["source_format"],
        document_type=chunk["document_type"],
        locator=ChunkLocator(**locator),
        element_ids=chunk.get("element_ids", []),
        metadata=chunk.get("metadata", {}),
    )


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected_source_ids = {record["source_id"] for record in registry["records"]}
    representatives = _representative_by_source()
    renderer = DocumentCitationRenderer()
    failures: list[dict[str, object]] = []
    scope_counts: Counter[str] = Counter()
    identity_counts: Counter[str] = Counter()

    for source_id, chunk in sorted(representatives.items()):
        context = _context(chunk)
        try:
            rendered = renderer.render([context])
            if len(rendered) != 1:
                raise AssertionError(f"expected one rendered citation, got {len(rendered)}")
            citation = rendered[0]
            display = citation.display()
            trace = citation.trace_dict()
            if context.chunk_id in display or context.source_id in display:
                raise AssertionError("internal identifier exposed in citation display")
            if citation.source_path != context.source_path or citation.source_id != context.source_id:
                raise AssertionError("rendered source identity mismatch")
            if citation.citation_scope == "document_location" and "locator" not in trace:
                raise AssertionError("located citation missing trace locator")
            if citation.citation_scope == "document" and "locator" in trace:
                raise AssertionError("document-level citation unexpectedly has a locator")
            scope_counts[citation.citation_scope] += 1
            identity_counts["document_id" if citation.document_id else "source_filename"] += 1
        except Exception as error:  # Audit must report all failed sources.
            failures.append({"source_id": source_id, "source_path": chunk["source_path"], "error": str(error)})

    missing_registry_sources = sorted(expected_source_ids - set(representatives))
    extra_corpus_sources = sorted(set(representatives) - expected_source_ids)
    rendered_count = len(representatives) - len(failures)
    audit = {
        "schema_version": "1.0",
        "purpose": "Host-only runtime citation renderability audit",
        "inputs": {
            "corpus": str(CORPUS.relative_to(ROOT)),
            "corpus_sha256": _sha256(CORPUS),
            "registry": str(REGISTRY.relative_to(ROOT)),
            "registry_sha256": _sha256(REGISTRY),
        },
        "contract": {
            "identity_priority": [
                "verified document_id + locator",
                "original source filename + locator",
                "original source filename document-level",
            ],
            "raw_chunk_id_user_facing": False,
            "raw_source_id_user_facing": False,
        },
        "coverage": {
            "runtime_source_count": len(expected_source_ids),
            "representative_source_count": len(representatives),
            "rendered_source_count": rendered_count,
            "failed_source_count": len(failures),
            "missing_registry_source_count": len(missing_registry_sources),
            "extra_corpus_source_count": len(extra_corpus_sources),
            "citation_scope_counts": dict(sorted(scope_counts.items())),
            "identity_counts": dict(sorted(identity_counts.items())),
        },
        "failures": failures,
        "gate": {
            "decision": "PASS" if rendered_count == len(expected_source_ids) and not failures and not missing_registry_sources and not extra_corpus_sources else "BLOCKED",
            "reasons": [] if rendered_count == len(expected_source_ids) and not failures and not missing_registry_sources and not extra_corpus_sources else ["runtime source citation renderability audit failed"],
        },
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "coverage": audit["coverage"], "gate": audit["gate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
