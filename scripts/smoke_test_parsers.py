"""Parse every supported source document and report parser health."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.ingestion.registry import ParserRegistry, build_default_registry
from src.ingestion.validation import validate_parsed_document
from src.models.document import DocumentType, ElementType


NATIVE_TEXT_MISSING_PAGE_PATTERN = re.compile(
    r"^page \d+: usable native text block 없음$"
)
SUCCESS_STATUSES = {"success", "success_with_warnings"}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run parser and locator-invariant smoke tests on the corpus."
    )
    parser.add_argument("--source-root", default=None)
    parser.add_argument(
        "--output", default="data/diagnostics/parser_smoke_test.jsonl"
    )
    parser.add_argument(
        "--summary", default="docs/parser_smoke_test_report.md"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--date-candidate-threshold",
        type=int,
        default=20,
        help="List documents with at least this many date candidates.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    load_dotenv()
    source_root_value = args.source_root or os.getenv("PENSION_DATA_ROOT")
    if not source_root_value:
        raise RuntimeError("PENSION_DATA_ROOT is not configured.")

    source_root = Path(source_root_value).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    registry = build_default_registry()
    paths = sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in registry.supported_extensions
    )
    if args.limit is not None:
        paths = paths[: args.limit]

    output_path = _resolve_project_path(args.output)
    summary_path = _resolve_project_path(args.summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for index, path in enumerate(paths, start=1):
        relative_path = path.relative_to(source_root).as_posix()
        print(f"[{index}/{len(paths)}] {relative_path}", flush=True)
        result = _parse_one(
            registry=registry,
            path=path,
            source_root=source_root,
            relative_path=relative_path,
            fail_fast=args.fail_fast,
        )
        results.append(result)

    _write_jsonl(results, output_path)
    write_summary(
        results=results,
        summary_path=summary_path,
        source_root=source_root,
        date_candidate_threshold=args.date_candidate_threshold,
    )


def _parse_one(
    registry: ParserRegistry,
    path: Path,
    source_root: Path,
    relative_path: str,
    fail_fast: bool,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    try:
        document = registry.get_parser(path).parse(
            path=path,
            source_root=source_root,
        )
        validation_errors = validate_parsed_document(document)
        text_count = sum(
            element.kind != ElementType.TABLE for element in document.elements
        )
        table_count = sum(
            element.kind == ElementType.TABLE for element in document.elements
        )
        native_text_missing_page_count = sum(
            bool(NATIVE_TEXT_MISSING_PAGE_PATTERN.match(warning))
            for warning in document.warnings
        )
        if validation_errors:
            status = "invalid"
        elif not document.elements:
            status = "empty"
        elif document.warnings:
            status = "success_with_warnings"
        else:
            status = "success"
        return {
            "relative_path": relative_path,
            "extension": path.suffix.lower(),
            "source_id": document.source_id,
            "source_format": document.source_format.value,
            "document_type": document.document_type.value,
            "status": status,
            "elapsed_ms": _elapsed_ms(started_at),
            "element_count": len(document.elements),
            "text_element_count": text_count,
            "table_element_count": table_count,
            "native_text_missing_page_count": native_text_missing_page_count,
            "warning_count": len(document.warnings),
            "warnings": document.warnings,
            "validation_error_count": len(validation_errors),
            "validation_errors": validation_errors,
            "product_code_count": len(document.product_codes),
            "date_candidate_count": len(document.date_candidates),
        }
    except Exception as exc:
        if fail_fast:
            raise
        return {
            "relative_path": relative_path,
            "extension": path.suffix.lower(),
            "status": "failed",
            "elapsed_ms": _elapsed_ms(started_at),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def _elapsed_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def _write_jsonl(results: Sequence[Dict[str, Any]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def write_summary(
    results: Sequence[Dict[str, Any]],
    summary_path: Path,
    source_root: Path,
    date_candidate_threshold: int,
) -> None:
    status_counts = Counter(result["status"] for result in results)
    extension_results: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for result in results:
        extension_results[result["extension"]].append(result)

    flagged_results = [
        result
        for result in results
        if result["status"] in {"failed", "invalid", "empty"}
    ]
    documents_with_tables = sum(
        result.get("table_element_count", 0) > 0 for result in results
    )
    product_documents = [
        result
        for result in results
        if result.get("document_type") == DocumentType.INVESTMENT_PRODUCT.value
    ]
    product_documents_with_codes = sum(
        result.get("product_code_count", 0) > 0 for result in product_documents
    )
    high_date_documents = sorted(
        (
            result
            for result in results
            if result.get("date_candidate_count", 0) >= date_candidate_threshold
        ),
        key=lambda result: (-result.get("date_candidate_count", 0), result["relative_path"]),
    )
    warning_leaders = sorted(
        results,
        key=lambda result: (-result.get("warning_count", 0), result["relative_path"]),
    )[:10]
    total_elapsed_ms = sum(result.get("elapsed_ms", 0) for result in results)

    lines = [
        "# 파서 Smoke Test 보고서",
        "",
        f"- 원본 루트: `{_display_path(source_root)}`",
        f"- 검사 문서 수: {len(results)}개",
        f"- 총 소요 시간: {total_elapsed_ms / 1000:.2f}초",
        "- JSONL 상세 결과: `data/diagnostics/parser_smoke_test.jsonl`(Git 제외)",
        "",
        "## 상태",
        "",
        "| 상태 | 개수 |",
        "|---|---:|",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## 확장자별 성능",
            "",
            "| 확장자 | 검사 수 | 성공 수 | 성공률 | 평균 시간 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for extension, extension_items in sorted(extension_results.items()):
        successful = sum(item["status"] in SUCCESS_STATUSES for item in extension_items)
        average_ms = sum(item.get("elapsed_ms", 0) for item in extension_items) / len(extension_items)
        lines.append(
            f"| {extension} | {len(extension_items)} | {successful} | "
            f"{successful / len(extension_items):.1%} | {average_ms:.2f} ms |"
        )

    lines.extend(
        [
            "",
            "## 코퍼스 신호",
            "",
            f"- 표 요소를 포함한 문서: {documents_with_tables}개",
            "- 네이티브 텍스트가 없는 PDF 페이지: "
            f"{sum(result.get('native_text_missing_page_count', 0) for result in results)}",
            f"- 전체 요소: {sum(result.get('element_count', 0) for result in results)}개",
            "- 전체 표 요소: "
            f"{sum(result.get('table_element_count', 0) for result in results)}",
        ]
    )
    if product_documents:
        lines.append(
            "- 상품코드가 추출된 상품 문서: "
            f"{product_documents_with_codes}/{len(product_documents)} "
            f"({product_documents_with_codes / len(product_documents):.1%})"
        )
    else:
        lines.append("- 상품코드가 추출된 상품 문서: 파싱한 상품 문서 없음")

    lines.extend(["", "## 실패·검증 오류·빈 문서", ""])
    if flagged_results:
        for result in flagged_results:
            detail = result.get("error_type") or "추출 가능한 요소 없음"
            lines.append(
                f"- `{_escape_markdown(result['relative_path'])}`: "
                f"{result['status']} ({_escape_markdown(detail)})"
            )
    else:
        lines.append("없음.")

    lines.extend(
        [
            "",
            f"## 날짜 후보가 {date_candidate_threshold}개 이상인 문서",
            "",
        ]
    )
    if high_date_documents:
        for result in high_date_documents:
            lines.append(
                f"- `{_escape_markdown(result['relative_path'])}`: "
                f"{result['date_candidate_count']}"
            )
    else:
        lines.append("없음.")

    lines.extend(["", "## 경고가 많은 문서 상위 10개", ""])
    lines.extend(
        ["| 상대 경로 | 경고 수 |", "|---|---:|"]
        if warning_leaders
        else ["없음."]
    )
    for result in warning_leaders:
        lines.append(
            f"| `{_escape_markdown(result['relative_path'])}` | "
            f"{result.get('warning_count', 0)} |"
        )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.name


def _escape_markdown(value: Any) -> str:
    return str(value).replace("|", "\\|")


if __name__ == "__main__":
    main()
