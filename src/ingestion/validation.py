"""Schema and source-location invariants for parsed documents."""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

from src.models.document import (
    ElementType,
    Locator,
    ParsedDocument,
    SourceFormat,
)


FORMAT_EXTENSIONS = {
    SourceFormat.PDF: ".pdf",
    SourceFormat.DOCX: ".docx",
    SourceFormat.PPTX: ".pptx",
    SourceFormat.XLSX: ".xlsx",
}


def validate_parsed_document(document: ParsedDocument) -> List[str]:
    """Return invariant violations without preventing diagnostic collection."""
    errors: List[str] = []

    if not document.source_id:
        errors.append("source_id is empty")
    if not document.relative_path:
        errors.append("relative_path is empty")

    expected_extension = FORMAT_EXTENSIONS[document.source_format]
    actual_extension = Path(document.relative_path).suffix.lower()
    if actual_extension != expected_extension:
        errors.append(
            "source_format extension mismatch: "
            f"format={document.source_format.value}, extension={actual_extension}"
        )

    element_ids: Set[str] = set()
    for expected_order, element in enumerate(document.elements):
        if element.element_id in element_ids:
            errors.append(f"duplicate element_id: {element.element_id}")
        element_ids.add(element.element_id)

        if element.order != expected_order:
            errors.append(
                "non-contiguous order: "
                f"expected={expected_order}, actual={element.order}"
            )

        if element.kind == ElementType.TABLE and element.table is None:
            errors.append(f"table missing: {element.element_id}")
        if element.kind != ElementType.TABLE and not element.text:
            errors.append(f"text missing: {element.element_id}")

        errors.extend(
            _validate_locator(
                document.source_format,
                element.element_id,
                element.locator,
            )
        )

    try:
        document.model_dump_json()
    except Exception as exc:
        errors.append(
            "JSON serialization failed: " f"{type(exc).__name__}: {exc}"
        )

    return errors


def _validate_locator(
    source_format: SourceFormat,
    element_id: str,
    locator: Locator,
) -> List[str]:
    errors: List[str] = []

    if source_format == SourceFormat.PDF:
        if locator.page is None:
            errors.append(f"PDF page missing: {element_id}")
        if locator.slide is not None:
            errors.append(f"PDF has unexpected slide: {element_id}")
        if locator.sheet is not None:
            errors.append(f"PDF has unexpected sheet: {element_id}")
    elif source_format == SourceFormat.DOCX:
        if locator.block_index is None:
            errors.append(f"DOCX block_index missing: {element_id}")
        if locator.page is not None:
            errors.append(f"DOCX has invented page: {element_id}")
        if locator.slide is not None:
            errors.append(f"DOCX has unexpected slide: {element_id}")
        if locator.sheet is not None:
            errors.append(f"DOCX has unexpected sheet: {element_id}")
    elif source_format == SourceFormat.PPTX:
        if locator.slide is None:
            errors.append(f"PPTX slide missing: {element_id}")
        if locator.page is not None:
            errors.append(f"PPTX has unexpected page: {element_id}")
        if locator.sheet is not None:
            errors.append(f"PPTX has unexpected sheet: {element_id}")
    elif source_format == SourceFormat.XLSX:
        if not locator.sheet:
            errors.append(f"XLSX sheet missing: {element_id}")
        if not locator.cell_range:
            errors.append(f"XLSX cell_range missing: {element_id}")
        if locator.page is not None:
            errors.append(f"XLSX has unexpected page: {element_id}")
        if locator.slide is not None:
            errors.append(f"XLSX has unexpected slide: {element_id}")

    return errors
