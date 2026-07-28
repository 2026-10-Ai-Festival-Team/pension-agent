from pathlib import Path

import pymupdf

from src.ingestion.pdf_parser import PdfParser
from src.models.document import ElementType, SourceFormat


def create_sample_pdf(path: Path) -> None:
    document = pymupdf.open()
    page1 = document.new_page()
    page1.insert_text((72, 72), "퇴직연금 안내\n기준일: 2026.01.01")
    page2 = document.new_page()
    page2.insert_text((72, 72), "DB와 DC의 차이를 설명합니다.")
    document.save(path)
    document.close()


def test_pdf_parser_preserves_page_locator(tmp_path: Path) -> None:
    source_root = tmp_path / "raw"
    source_root.mkdir()
    pdf_path = source_root / "sample.pdf"
    create_sample_pdf(pdf_path)

    result = PdfParser().parse(pdf_path, source_root)

    assert result.source_format == SourceFormat.PDF
    assert result.relative_path == "sample.pdf"
    assert result.elements
    pages = {element.locator.page for element in result.elements if element.kind != ElementType.TABLE}
    assert pages == {1, 2}


def test_pdf_parser_extracts_date_candidate(tmp_path: Path) -> None:
    source_root = tmp_path / "raw"
    source_root.mkdir()
    pdf_path = source_root / "sample.pdf"
    create_sample_pdf(pdf_path)

    result = PdfParser().parse(pdf_path, source_root)

    assert "2026.01.01" in result.date_candidates


def test_pdf_parser_serializes_to_json(tmp_path: Path) -> None:
    source_root = tmp_path / "raw"
    source_root.mkdir()
    pdf_path = source_root / "sample.pdf"
    create_sample_pdf(pdf_path)

    serialized = PdfParser().parse(pdf_path, source_root).model_dump_json()

    assert '"schema_version":"1.0"' in serialized


def test_pdf_parser_warns_for_page_without_usable_text(tmp_path: Path) -> None:
    source_root = tmp_path / "raw"
    source_root.mkdir()
    pdf_path = source_root / "blank.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(pdf_path)
    document.close()

    result = PdfParser().parse(pdf_path, source_root)

    assert result.warnings == ["page 1: usable native text block 없음"]
