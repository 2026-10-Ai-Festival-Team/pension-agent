"""Classify native-text-absent PDF pages for manual OCR triage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pymupdf
from dotenv import load_dotenv

from src.ingestion.common import make_source_id, normalize_text, relative_path


DEFAULT_COVERAGE_THRESHOLD = 0.35


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify PDF pages that merit OCR, without performing OCR."
    )
    parser.add_argument("--source-root", default=None)
    parser.add_argument(
        "--output", default="data/diagnostics/ocr_candidates.jsonl"
    )
    parser.add_argument("--summary", default="docs/ocr_triage_report.md")
    parser.add_argument(
        "--image-coverage-threshold",
        type=float,
        default=DEFAULT_COVERAGE_THRESHOLD,
    )
    parser.add_argument(
        "--manual-ocr-candidate",
        action="append",
        default=[],
        metavar="RELATIVE_PATH:PAGE",
        help="Mark a visually verified, content-bearing page as an OCR candidate.",
    )
    parser.add_argument(
        "--manual-note",
        action="append",
        default=[],
        metavar="RELATIVE_PATH:NOTE",
        help="Record a visual-inspection finding in the Markdown report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not 0 < args.image_coverage_threshold <= 1:
        raise ValueError("--image-coverage-threshold must be in (0, 1].")
    manual_candidates = _parse_manual_candidates(args.manual_ocr_candidate)
    manual_notes = _parse_manual_notes(args.manual_note)

    load_dotenv()
    source_root_value = args.source_root or os.getenv("PENSION_DATA_ROOT")
    if not source_root_value:
        raise RuntimeError("PENSION_DATA_ROOT is not configured.")
    source_root = Path(source_root_value).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    records: List[Dict[str, Any]] = []
    document_summaries: List[Dict[str, Any]] = []
    pdf_paths = sorted(path for path in source_root.rglob("*") if path.suffix.lower() == ".pdf")
    for index, path in enumerate(pdf_paths, start=1):
        relative = relative_path(path, source_root)
        print(f"[{index}/{len(pdf_paths)}] {relative}", flush=True)
        page_records, document_summary = analyze_pdf(
            path=path,
            source_root=source_root,
            image_coverage_threshold=args.image_coverage_threshold,
            manual_candidates=manual_candidates,
        )
        records.extend(page_records)
        document_summaries.append(document_summary)

    output_path = _resolve_project_path(args.output)
    summary_path = _resolve_project_path(args.summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(records, output_path)
    write_report(
        records=records,
        document_summaries=document_summaries,
        summary_path=summary_path,
        image_coverage_threshold=args.image_coverage_threshold,
        manual_notes=manual_notes,
    )
    print(f"Native-text-absent pages: {len(records)}")
    print(f"OCR candidates: {sum(record['ocr_candidate'] for record in records)}")


def analyze_pdf(
    path: Path,
    source_root: Path,
    image_coverage_threshold: float,
    manual_candidates: Sequence[Tuple[str, int]] = (),
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Return records only for pages that have no usable native text."""
    relative = relative_path(path, source_root)
    source_id = make_source_id(relative)
    document = pymupdf.open(path)
    try:
        page_texts = [normalize_text(page.get_text("text")) for page in document]
        has_native_text_after_first_page = any(page_texts[1:])
        records: List[Dict[str, Any]] = []
        for page_index, page in enumerate(document):
            native_text_length = len(page_texts[page_index])
            if native_text_length:
                continue
            image_rects = _image_rectangles(page)
            image_coverage_ratio = _coverage_ratio(
                image_rects=image_rects,
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
            )
            is_likely_cover = (
                page_index == 0
                and has_native_text_after_first_page
                and image_coverage_ratio >= image_coverage_threshold
            )
            ocr_candidate, reason = classify_ocr_candidate(
                native_text_length=native_text_length,
                image_count=len(image_rects),
                image_coverage_ratio=image_coverage_ratio,
                is_likely_cover=is_likely_cover,
                coverage_threshold=image_coverage_threshold,
            )
            if (relative, page_index + 1) in manual_candidates:
                ocr_candidate = True
                reason = "manual_verified_content"
            records.append(
                {
                    "source_id": source_id,
                    "relative_path": relative,
                    "page": page_index + 1,
                    "native_text_length": native_text_length,
                    "image_count": len(image_rects),
                    "image_coverage_ratio": round(image_coverage_ratio, 4),
                    "page_width": round(float(page.rect.width), 2),
                    "page_height": round(float(page.rect.height), 2),
                    "ocr_candidate": ocr_candidate,
                    "reason": reason,
                }
            )
        return records, {
            "source_id": source_id,
            "relative_path": relative,
            "page_count": len(document),
            "native_text_page_count": sum(bool(value) for value in page_texts),
            "native_text_absent_page_count": len(records),
            "ocr_candidate_page_count": sum(record["ocr_candidate"] for record in records),
        }
    finally:
        document.close()


def classify_ocr_candidate(
    native_text_length: int,
    image_count: int,
    image_coverage_ratio: float,
    is_likely_cover: bool,
    coverage_threshold: float,
) -> Tuple[bool, str]:
    """Conservatively classify a no-text page; OCR is never performed here."""
    if native_text_length:
        return False, "native_text_available"
    if is_likely_cover:
        return False, "likely_cover_page"
    if image_count == 0:
        return False, "no_native_text_without_embedded_image"
    if image_coverage_ratio >= coverage_threshold:
        return True, "no_native_text_high_image_coverage"
    return False, "no_native_text_low_image_coverage"


def _image_rectangles(page: pymupdf.Page) -> List[Tuple[float, float, float, float]]:
    rectangles: List[Tuple[float, float, float, float]] = []
    for image in page.get_image_info(xrefs=True):
        bbox = image.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        rectangles.append(tuple(float(value) for value in bbox))
    return rectangles


def _coverage_ratio(
    image_rects: Iterable[Tuple[float, float, float, float]],
    page_width: float,
    page_height: float,
) -> float:
    if page_width <= 0 or page_height <= 0:
        return 0.0
    clipped = []
    for x0, y0, x1, y1 in image_rects:
        left, right = sorted((max(0.0, x0), min(page_width, x1)))
        top, bottom = sorted((max(0.0, y0), min(page_height, y1)))
        if right > left and bottom > top:
            clipped.append((left, top, right, bottom))
    return min(1.0, _union_area(clipped) / (page_width * page_height))


def _union_area(rectangles: Sequence[Tuple[float, float, float, float]]) -> float:
    """Compute the union area of axis-aligned rectangles without double-counting."""
    x_values = sorted({value for rectangle in rectangles for value in (rectangle[0], rectangle[2])})
    area = 0.0
    for left, right in zip(x_values, x_values[1:]):
        if right <= left:
            continue
        intervals = sorted(
            (top, bottom)
            for x0, top, x1, bottom in rectangles
            if x0 < right and x1 > left
        )
        covered_height = 0.0
        current_top = current_bottom = None
        for top, bottom in intervals:
            if current_top is None:
                current_top, current_bottom = top, bottom
            elif top > current_bottom:
                covered_height += current_bottom - current_top
                current_top, current_bottom = top, bottom
            else:
                current_bottom = max(current_bottom, bottom)
        if current_top is not None:
            covered_height += current_bottom - current_top
        area += (right - left) * covered_height
    return area


def write_report(
    records: Sequence[Dict[str, Any]],
    document_summaries: Sequence[Dict[str, Any]],
    summary_path: Path,
    image_coverage_threshold: float,
    manual_notes: Sequence[Tuple[str, str]],
) -> None:
    reason_counts = Counter(record["reason"] for record in records)
    candidates_by_document: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["ocr_candidate"]:
            candidates_by_document[record["relative_path"]].append(record)
    empty_documents = [
        summary
        for summary in document_summaries
        if summary["native_text_page_count"] == 0
    ]
    lines = [
        "# OCR Triage Report",
        "",
        "## Scope and rule",
        "",
        f"- PDFs inspected: {len(document_summaries)}",
        f"- Native-text-absent pages: {len(records)}",
        f"- OCR candidates: {sum(record['ocr_candidate'] for record in records)}",
        "- Rule: native text is absent, embedded-image coverage is at least "
        f"{image_coverage_threshold:.0%}, and the page is not a likely first-page cover.",
        "- `no_native_text_without_embedded_image` remains a manual-review item; "
        "it may be blank, vector-only, or a scanned page embedded in an unsupported form.",
        "",
        "## Classification reasons",
        "",
        "| Reason | Pages |",
        "|---|---:|",
    ]
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"| {reason} | {count} |")

    lines.extend(["", "## Native-text-empty documents", ""])
    if empty_documents:
        lines.extend(
            ["| Relative path | Pages | OCR-candidate pages |", "|---|---:|---:|"]
        )
        for summary in empty_documents:
            lines.append(
                f"| `{summary['relative_path']}` | {summary['page_count']} | "
                f"{summary['ocr_candidate_page_count']} |"
            )
    else:
        lines.append("None.")

    lines.extend(["", "## Manual visual inspection", ""])
    if manual_notes:
        for relative, note in manual_notes:
            lines.append(f"- `{relative}`: {note}")
    else:
        lines.append("Not recorded in this run.")

    lines.extend(["", "## Documents with OCR candidates", ""])
    if candidates_by_document:
        for relative, candidates in sorted(candidates_by_document.items()):
            pages = ", ".join(str(candidate["page"]) for candidate in candidates)
            lines.append(f"- `{relative}`: pages {pages}")
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Next action",
            "",
            "Use the OCR-candidate list as the review queue. Select an OCR engine only "
            "after spot-checking a small sample from each candidate group.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(records: Sequence[Dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _parse_manual_candidates(values: Sequence[str]) -> List[Tuple[str, int]]:
    candidates = []
    for value in values:
        relative, separator, page_value = value.rpartition(":")
        if not separator or not relative or not page_value.isdigit() or int(page_value) < 1:
            raise ValueError(
                "--manual-ocr-candidate must be RELATIVE_PATH:PAGE"
            )
        candidates.append((relative, int(page_value)))
    return candidates


def _parse_manual_notes(values: Sequence[str]) -> List[Tuple[str, str]]:
    notes = []
    for value in values:
        relative, separator, note = value.partition(":")
        if not separator or not relative or not note.strip():
            raise ValueError("--manual-note must be RELATIVE_PATH:NOTE")
        notes.append((relative, note.strip()))
    return notes


if __name__ == "__main__":
    main()
