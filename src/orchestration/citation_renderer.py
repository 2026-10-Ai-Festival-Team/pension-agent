"""Host-owned rendering of user-facing source citations.

``chunk_id`` and ``source_id`` are runtime identifiers, never presentation
identifiers. The renderer resolves each cited chunk through the immutable
runtime-source inventory and then renders the strongest authoritative identity
available: a verified DOC ID when one exists, otherwise the original source
filename. It never invents a DOC ID.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.generation.errors import CitationValidationError
from src.models.retrieval import SearchResult


_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data/provenance/runtime_citation_provenance_v2.json"


@dataclass(frozen=True)
class RenderedCitation:
    """A source-backed citation that is safe to show to a user."""

    source_id: str
    source_path: str
    source_filename: str
    document_id: str | None
    citation_scope: str
    location_kind: str | None
    location_value: str | int | None
    chunk_ids: tuple[str, ...]

    @property
    def identity(self) -> str:
        return self.document_id or self.source_filename

    def display(self) -> str:
        if self.citation_scope == "document":
            return f"- [{self.identity}]"
        assert self.location_kind is not None and self.location_value is not None
        if self.location_kind == "page":
            location = f"p.{self.location_value}"
        elif self.location_kind == "slide":
            location = f"slide {self.location_value}"
        else:
            location = f"sheet {self.location_value}"
        return f"- [{self.identity}, {location}]"

    def trace_dict(self) -> dict[str, object]:
        """Keep internal provenance in trace, separate from final answer."""
        trace: dict[str, object] = {
            "chunk_ids": list(self.chunk_ids),
            "source_id": self.source_id,
            "source_path": self.source_path,
            "source_filename": self.source_filename,
            "document_id": self.document_id,
            "citation_scope": self.citation_scope,
        }
        if self.location_kind is not None:
            trace["locator"] = {self.location_kind: self.location_value}
        return trace


class DocumentCitationRenderer:
    """Resolve citations via the authoritative runtime source inventory.

    The registry proves that each runtime ``source_id`` maps to one original
    source path. DOC IDs are optional enrichment, not a prerequisite for a
    compliant source citation. Unknown or mismatched source provenance remains
    fail-closed.
    """

    def __init__(self, source_to_document_id: dict[str, str] | None = None) -> None:
        self._source_to_document_id = source_to_document_id or {}
        self._registry = self._load_registry()

    @staticmethod
    def _load_registry() -> dict[str, dict[str, object]]:
        payload = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        inputs = payload.get("inputs", {})
        expected_hash = inputs.get("authoritative_bridge_sha256")
        relative_path = inputs.get("authoritative_bridge")
        if expected_hash and relative_path:
            bridge_path = Path(__file__).resolve().parents[2] / str(relative_path)
            actual_hash = hashlib.sha256(bridge_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError("runtime citation provenance source-bridge hash mismatch")

        records: dict[str, dict[str, object]] = {}
        for record in payload.get("records", []):
            source_id = record.get("source_id")
            source_path = record.get("source_path")
            if not isinstance(source_id, str) or not source_id or not isinstance(source_path, str) or not source_path:
                raise RuntimeError("runtime citation provenance registry contains invalid source identity")
            if source_id in records:
                raise RuntimeError(f"duplicate runtime citation provenance for {source_id}")
            document_id = record.get("document_id")
            if document_id is not None and (not isinstance(document_id, str) or not document_id.startswith("DOC-")):
                raise RuntimeError(f"invalid verified document ID for {source_id}")
            records[source_id] = record
        return records

    @staticmethod
    def _location(context: SearchResult) -> tuple[str, str | int] | None:
        locator = context.locator
        if locator.page_start is not None:
            if locator.page_end is not None and locator.page_end != locator.page_start:
                return "page", f"{locator.page_start}–{locator.page_end}"
            return "page", locator.page_start
        if locator.slide_start is not None:
            return "slide", locator.slide_start
        if locator.sheet:
            value = locator.sheet
            if locator.cell_range:
                value = f"{value} / {locator.cell_range}"
            return "sheet", value
        return None

    def _source_record(self, context: SearchResult) -> dict[str, object]:
        record = self._registry.get(context.source_id)
        if record is None:
            # Some controlled integrations supply an authoritative document
            # registry upstream of retrieval. That registry may not be part of
            # this frozen corpus inventory, but its explicit DOC identity plus
            # original path is still a valid source identity. This is not a
            # fallback for a missing DOC ID: absent both authorities, fail.
            metadata_document_id = context.metadata.get("document_id")
            if isinstance(metadata_document_id, str) and metadata_document_id.startswith("DOC-") and context.source_path:
                return {
                    "source_id": context.source_id,
                    "source_path": context.source_path,
                    "document_id": metadata_document_id,
                    "mapping_status": "upstream_authoritative_document_id",
                }
            raise CitationValidationError(
                "cited chunk source is absent from the runtime provenance registry",
                diagnostic={
                    "citation_validation_reason": "citation_provenance_source_unknown",
                    "chunk_id": context.chunk_id,
                    "source_id": context.source_id,
                    "source_path": context.source_path,
                },
            )
        if context.source_path != record["source_path"]:
            raise CitationValidationError(
                "cited chunk source path does not match runtime provenance",
                diagnostic={
                    "citation_validation_reason": "citation_provenance_mismatch",
                    "chunk_id": context.chunk_id,
                    "source_id": context.source_id,
                    "source_path": context.source_path,
                    "expected_source_path": record["source_path"],
                },
            )
        return record

    def render(self, cited_contexts: Iterable[SearchResult]) -> tuple[RenderedCitation, ...]:
        """Render source/location citations, failing only for identity failures."""
        merged: dict[tuple[str, str, str | int | None], RenderedCitation] = {}
        for context in cited_contexts:
            record = self._source_record(context)
            source_path = str(record["source_path"])
            source_filename = Path(source_path).name
            if not source_filename:
                raise CitationValidationError(
                    "cited chunk source has no displayable original filename",
                    diagnostic={
                        "citation_validation_reason": "citation_provenance_source_unknown",
                        "chunk_id": context.chunk_id,
                        "source_id": context.source_id,
                    },
                )
            document_id = record.get("document_id") or self._source_to_document_id.get(context.source_id)
            if document_id is not None and (not isinstance(document_id, str) or not document_id.startswith("DOC-")):
                raise CitationValidationError(
                    "citation has an invalid document ID",
                    diagnostic={"citation_validation_reason": "citation_provenance_invalid_document_id", "chunk_id": context.chunk_id},
                )
            location = self._location(context)
            if location is None:
                scope, location_kind, location_value = "document", None, None
            else:
                scope, (location_kind, location_value) = "document_location", location
            key = context.source_id, scope, location_value
            existing = merged.get(key)
            if existing is None:
                merged[key] = RenderedCitation(
                    source_id=context.source_id,
                    source_path=source_path,
                    source_filename=source_filename,
                    document_id=document_id,
                    citation_scope=scope,
                    location_kind=location_kind,
                    location_value=location_value,
                    chunk_ids=(context.chunk_id,),
                )
            else:
                merged[key] = RenderedCitation(
                    source_id=existing.source_id,
                    source_path=existing.source_path,
                    source_filename=existing.source_filename,
                    document_id=existing.document_id,
                    citation_scope=existing.citation_scope,
                    location_kind=existing.location_kind,
                    location_value=existing.location_value,
                    chunk_ids=existing.chunk_ids + (context.chunk_id,),
                )
        return tuple(merged.values())


def strip_model_citation_block(answer: str) -> str:
    """Remove a model-supplied citation section before host rendering."""
    text = answer.strip()
    if text.startswith("[답변]"):
        text = text[len("[답변]"):].lstrip("\n ")
    for marker in ("\n[근거]", "\n\n[근거]", "[근거]"):
        position = text.find(marker)
        if position >= 0:
            text = text[:position].rstrip()
            break
    return text


def assert_no_raw_chunk_ids(answer: str, contexts: Iterable[SearchResult]) -> None:
    """Fail closed if an internal retrieval or source ID would reach a user."""
    context_list = list(contexts)
    exposed_chunks = [context.chunk_id for context in context_list if context.chunk_id in answer]
    exposed_sources = [context.source_id for context in context_list if context.source_id in answer]
    if exposed_chunks or exposed_sources:
        raise CitationValidationError(
            "internal evidence identifier would be exposed in the user-facing answer",
            diagnostic={
                "citation_validation_reason": "user_facing_internal_id",
                "raw_chunk_ids": exposed_chunks,
                "raw_source_ids": exposed_sources,
            },
        )
