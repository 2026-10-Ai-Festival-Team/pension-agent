"""Build representative search chunks without running OCR or retrieval."""
import argparse
import csv
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from src.ingestion.registry import build_default_registry
from src.models.document import AuthorityLevel, SourceType
from src.preprocessing.corpus_builder import CorpusBuilder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default=None)
    parser.add_argument("--representative-csv", default="data/representative_documents.csv")
    parser.add_argument("--output", default="data/parsed/representative_chunks.jsonl")
    parser.add_argument("--report", default="docs/representative_corpus_report.md")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--source-type", choices=[item.value for item in SourceType], default=SourceType.ORIGINAL.value)
    parser.add_argument("--authority-level", choices=[item.value for item in AuthorityLevel], default=AuthorityLevel.PRIMARY.value)
    parser.add_argument("--as-of-date", default=None, help="원천 전체에 적용할 기준일(YYYY-MM-DD)")
    args = parser.parse_args()
    load_dotenv()
    root = Path(args.source_root or os.environ["PENSION_DATA_ROOT"]).resolve()
    paths = _paths(root, Path(args.representative_csv), args.all)
    builder = CorpusBuilder(build_default_registry())
    chunks, empty_documents = [], []
    for path in paths:
        built = builder.build_document(
            path,
            root,
            source_type=SourceType(args.source_type),
            authority_level=AuthorityLevel(args.authority_level),
            as_of_date=args.as_of_date,
        )
        if not built:
            empty_documents.append(path.relative_to(root).as_posix())
        chunks.extend(built)
    output, report = Path(args.output), Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            file.write(chunk.model_dump_json() + "\n")
    _write_report(
        report,
        chunks,
        Counter(path.suffix.lower() for path in paths),
        empty_documents,
        _ocr_records(),
    )
    print(f"처리 문서: {len(paths)}개, 생성 청크: {len(chunks)}개")


def _paths(root: Path, representative_csv: Path, build_all: bool):
    if build_all:
        return sorted(path for path in root.rglob("*") if path.suffix.lower() in {".pdf", ".docx", ".pptx", ".xlsx"})
    with representative_csv.open(encoding="utf-8-sig", newline="") as file:
        return [root / row["relative_path"] for row in csv.DictReader(file)]


def _ocr_records():
    path = Path("data/diagnostics/ocr_candidates.jsonl")
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def _write_report(report: Path, chunks, document_formats, empty_documents, ocr_records) -> None:
    lengths = [len(chunk.text) for chunk in chunks]
    ids = [chunk.chunk_id for chunk in chunks]
    by_format = Counter(chunk.source_format for chunk in chunks)
    by_type = Counter(chunk.chunk_type.value for chunk in chunks)
    missing_locator = sum(chunk.locator is None for chunk in chunks)
    missing_elements = sum(not chunk.element_ids for chunk in chunks)
    missing_codes = sum(chunk.document_type == "investment_product" and not chunk.product_codes for chunk in chunks)
    by_source = {}
    for chunk in chunks:
        by_source.setdefault(chunk.source_path, []).append(chunk)
    partial_documents = {item["relative_path"] for item in ocr_records if item["relative_path"] not in empty_documents}
    lines = ["# 전체 Corpus 생성 보고서", "", f"- 처리 문서 수: {sum(document_formats.values())}개", f"- 생성 청크 수: {len(chunks)}개", f"- 빈 청크 수: {sum(not chunk.text.strip() for chunk in chunks)}개", f"- 중복 chunk_id 수: {len(ids) - len(set(ids))}개", f"- locator 누락 수: {missing_locator}개", f"- element_ids 누락 수: {missing_elements}개", f"- 상품코드 누락 청크 수: {missing_codes}개", "", "## OCR 상태", "", f"- OCR 후보 페이지: {sum(item.get('ocr_candidate', False) for item in ocr_records)}개", f"- OCR 보류 문서: {len(empty_documents)}개", f"- 부분 네이티브 텍스트 문서: {len(partial_documents)}개", "", "## 형식별 문서 수", ""]
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(document_formats.items()))
    lines.extend(["", "## 형식별 청크 수", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(by_format.items()))
    lines.extend(["", "## 청크 유형별 수", ""])
    lines.extend(f"- `{key}`: {value}" for key, value in sorted(by_type.items()))
    lines.extend(["", "## 문자 수", "", f"- 평균: {statistics.mean(lengths):.1f}" if lengths else "- 평균: 0", f"- 중앙: {statistics.median(lengths):.1f}" if lengths else "- 중앙: 0", f"- 최대: {max(lengths) if lengths else 0}", "", "## 수동 검토 목록", ""])
    short_chunks = [chunk for chunk in chunks if len(chunk.text) < 500]
    long_chunks = [chunk for chunk in chunks if len(chunk.text) > 1500]
    lines.append(f"- 500자 미만 청크: {len(short_chunks)}개")
    lines.append(f"- 1,500자 초과 청크: {len(long_chunks)}개")
    lines.append("- 청크가 0개인 문서: " + (", ".join(f"`{item}`" for item in empty_documents) if empty_documents else "없음"))
    lines.extend(["", "## OCR 보류 문서", ""])
    lines.extend(f"- `{item}`" for item in empty_documents)
    if not empty_documents:
        lines.append("- 없음")
    lines.extend(["", "## 500자 미만 청크", ""])
    lines.extend(f"- `{chunk.chunk_id}` ({len(chunk.text)}자)" for chunk in short_chunks)
    lines.extend(["", "## 1,500자 초과 청크", ""])
    lines.extend(f"- `{chunk.chunk_id}` ({len(chunk.text)}자)" for chunk in long_chunks)
    lines.extend(["", "## 문서별 청크 수 상위 10개", ""])
    lines.extend(f"- `{path}`: {len(items)}" for path, items in sorted(by_source.items(), key=lambda item: -len(item[1]))[:10])
    lines.extend(["", "## 100자 미만 청크가 많은 문서 상위 10개", ""])
    lines.extend(f"- `{path}`: {sum(len(chunk.text) < 100 for chunk in items)}" for path, items in sorted(by_source.items(), key=lambda item: -sum(len(chunk.text) < 100 for chunk in item[1]))[:10])
    lines.extend(["", "## 1,500자 초과 청크가 많은 문서 상위 10개", ""])
    lines.extend(f"- `{path}`: {sum(len(chunk.text) > 1500 for chunk in items)}" for path, items in sorted(by_source.items(), key=lambda item: -sum(len(chunk.text) > 1500 for chunk in item[1]))[:10])
    lines.extend(["", "## 표 청크가 많은 문서 상위 10개", ""])
    lines.extend(f"- `{path}`: {sum(chunk.chunk_type.value == 'table' for chunk in items)}" for path, items in sorted(by_source.items(), key=lambda item: -sum(chunk.chunk_type.value == 'table' for chunk in item[1]))[:10])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
