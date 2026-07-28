"""Produce inventory statistics and a manual-review template from manifest metadata."""

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from check_data_path import get_data_root


MANIFEST_PATH = Path("data/manifest.csv")
REPORT_PATH = Path("data/inventory_report.md")
SAMPLES_PATH = Path("data/representative_documents.csv")
REQUIREMENTS_PATH = Path("data/representative_document_requirements.csv")
LARGE_FILE_BYTES = 100 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}

SAMPLE_FIELDS = ["file_id", "relative_path", "filename", "extension", "file_size", "product_code", "document_category", "sample_role", "selection_note"]
REQUIREMENT_FIELDS = [
    "file_id", "relative_path", "filename", "sample_role", "file_format", "page_count",
    "native_text_available", "scan_likelihood", "has_tables", "table_complexity", "has_images",
    "title_extractable", "section_structure", "page_number_preservable", "effective_date_found",
    "product_code_found", "header_footer_noise", "recommended_parser", "ocr_required",
    "review_notes", "review_status",
]


def read_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"매니페스트가 없습니다: {path}. 먼저 build_manifest.py를 실행하세요.")
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def file_size(row: Dict[str, str]) -> int:
    return int(row["file_size"])


def select_rows(rows: Sequence[Dict[str, str]], extension: str, count: int, used: set[str]) -> List[Dict[str, str]]:
    candidates = [row for row in rows if row["extension"] == extension and row["file_id"] not in used]
    candidates.sort(key=lambda row: (file_size(row), row["relative_path"]))
    selected = candidates[:count]
    used.update(row["file_id"] for row in selected)
    return selected


def select_representative_documents(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """Choose review candidates; classifications remain hypotheses until manual review."""
    used: set[str] = set()
    selections: List[tuple[Dict[str, str], str, str]] = []

    # Keep the two product-investment samples separate from the five general PDF roles.
    pdfs = [
        row for row in rows
        if row["extension"] == ".pdf" and row["document_category"] != "investment_product"
    ]
    if len(pdfs) < 5:
        pdfs.extend(
            row for row in rows
            if row["extension"] == ".pdf" and row["document_category"] == "investment_product"
        )
    pdfs.sort(key=lambda row: (file_size(row), row["relative_path"]))
    for row, role, note in zip(
        pdfs[:2],
        ["general_pdf_candidate", "general_pdf_candidate"],
        ["일반 텍스트 PDF 여부를 확인할 후보", "일반 텍스트 PDF 여부를 확인할 후보"],
    ):
        used.add(row["file_id"])
        selections.append((row, role, note))

    remaining_pdfs = [row for row in pdfs if row["file_id"] not in used]
    for row in remaining_pdfs[-2:]:
        used.add(row["file_id"])
        selections.append((row, "table_pdf_candidate", "표가 많은 PDF 여부를 확인할 후보"))
    remaining_pdfs = [row for row in pdfs if row["file_id"] not in used]
    if remaining_pdfs:
        row = remaining_pdfs[-1]
        used.add(row["file_id"])
        selections.append((row, "image_or_scan_pdf_candidate", "이미지·스캔 중심 PDF 여부를 확인할 후보"))

    for row in select_rows(rows, ".docx", 2, used):
        selections.append((row, "docx_candidate", "DOCX 구조 보존 가능성을 확인할 후보"))
    for row in select_rows(rows, ".pptx", 1, used):
        selections.append((row, "pptx_candidate", "PPTX 슬라이드·도형·표 처리를 확인할 후보"))
    for row in select_rows(rows, ".xlsx", 2, used):
        selections.append((row, "xlsx_candidate", "시트·병합 셀·수식·숨김 요소를 확인할 후보"))

    investments = [row for row in rows if row["document_category"] == "investment_product" and row["file_id"] not in used]
    investments.sort(key=lambda row: (row["extension"] not in SUPPORTED_EXTENSIONS, row["relative_path"]))
    for row in investments[:2]:
        used.add(row["file_id"])
        selections.append((row, "investment_product_candidate", "상품코드와 투자설명서 구조를 확인할 후보"))

    output: List[Dict[str, str]] = []
    for row, role, note in selections:
        output.append({
            **{field: row[field] for field in SAMPLE_FIELDS if field in row},
            "sample_role": role,
            "selection_note": note,
        })
    return output


def empty_directories(data_root: Path) -> List[str]:
    directories = [path for path in data_root.rglob("*") if path.is_dir()]
    directories_with_files: set[Path] = set()
    for file_path in data_root.rglob("*"):
        if file_path.is_file():
            current = file_path.parent
            while current != data_root.parent:
                directories_with_files.add(current)
                if current == data_root:
                    break
                current = current.parent
    return [path.relative_to(data_root).as_posix() for path in directories if path not in directories_with_files]


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: Sequence[Dict[str, str]], data_root: Path, path: Path) -> None:
    extensions = Counter(row["extension"] or "[no extension]" for row in rows)
    product_codes = {row["product_code"] for row in rows if row["product_code"]}
    filenames: dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        filenames[row["filename"].casefold()].append(row)
    duplicate_names = [group for group in filenames.values() if len(group) > 1]
    large_files = [row for row in rows if file_size(row) >= LARGE_FILE_BYTES]
    empty_dirs = empty_directories(data_root)

    lines = [
        "# 데이터 인벤토리 보고서", "", "## 범위", "",
        "이 보고서에는 메타데이터만 담는다. 경로는 `PENSION_DATA_ROOT` 기준 상대 경로이며 문서 내용이나 절대 경로는 저장하지 않는다.",
        "", "## 파일 형식별 수", "", "| 확장자 | 파일 수 |", "| --- | ---: |",
    ]
    lines.extend(f"| {extension} | {count} |" for extension, count in sorted(extensions.items()))
    lines.extend([
        "", "## 구조 점검", "",
        f"- 전체 파일: {len(rows)}개",
        f"- 파싱 대상 파일(`.pdf`, `.docx`, `.pptx`, `.xlsx`): {sum(row['extension'] in SUPPORTED_EXTENSIONS for row in rows)}개",
        f"- 파일이 있는 상품코드 폴더: {len(product_codes)}개",
        f"- 하위 파일이 없는 폴더: {len(empty_dirs)}개",
        f"- 중복 파일명(대소문자 무시): {len(duplicate_names)}개",
        f"- 대용량 파일({LARGE_FILE_BYTES // (1024 * 1024)}MiB 이상): {len(large_files)}개",
        "", "## 빈 폴더", "",
    ])
    lines.extend([f"- `{directory}`" for directory in empty_dirs] or ["- 없음"])
    lines.extend(["", "## 중복 파일명", ""])
    if duplicate_names:
        for group in duplicate_names:
            lines.append(f"- `{group[0]['filename']}` ({len(group)} files): " + ", ".join(f"`{row['relative_path']}`" for row in group))
    else:
        lines.append("- 없음")
    lines.extend(["", "## 대용량 파일", ""])
    if large_files:
        for row in sorted(large_files, key=file_size, reverse=True):
            lines.append(f"- `{row['relative_path']}` — {file_size(row) / (1024 * 1024):.1f} MiB")
    else:
        lines.append("- 없음")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def requirement_rows(samples: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    rows = []
    for sample in samples:
        rows.append({
            "file_id": sample["file_id"], "relative_path": sample["relative_path"], "filename": sample["filename"],
            "sample_role": sample["sample_role"], "file_format": sample["extension"], "page_count": "not_reviewed",
            "native_text_available": "not_reviewed", "scan_likelihood": "not_reviewed",
            "has_tables": "not_reviewed", "table_complexity": "not_reviewed", "has_images": "not_reviewed",
            "title_extractable": "not_reviewed", "section_structure": "not_reviewed",
            "page_number_preservable": "not_reviewed", "effective_date_found": "not_reviewed",
            "product_code_found": sample["product_code"] or "not_reviewed", "header_footer_noise": "not_reviewed",
            "recommended_parser": "not_reviewed", "ocr_required": "not_reviewed",
            "review_notes": sample["selection_note"], "review_status": "not_reviewed",
        })
    return rows


def main() -> None:
    data_root = get_data_root()
    rows = read_manifest(MANIFEST_PATH)
    write_report(rows, data_root, REPORT_PATH)
    samples = select_representative_documents(rows)
    write_csv(SAMPLES_PATH, SAMPLE_FIELDS, samples)
    write_csv(REQUIREMENTS_PATH, REQUIREMENT_FIELDS, requirement_rows(samples))
    print(f"인벤토리 보고서: {REPORT_PATH}")
    print(f"대표 문서 후보: {len(samples)}개 ({SAMPLES_PATH})")
    print(f"수동 검토표: {REQUIREMENTS_PATH}")


if __name__ == "__main__":
    main()
