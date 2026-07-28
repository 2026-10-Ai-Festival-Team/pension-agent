from pathlib import Path
from typing import Type

import pytest

from src.ingestion.docx_parser import DocxParser
from src.ingestion.pdf_parser import PdfParser
from src.ingestion.pptx_parser import PptxParser
from src.ingestion.registry import (
    DuplicateParserError,
    ParserRegistry,
    UnsupportedDocumentError,
    build_default_registry,
)
from src.ingestion.xlsx_parser import XlsxParser


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("sample.pdf", PdfParser),
        ("sample.docx", DocxParser),
        ("sample.pptx", PptxParser),
        ("sample.xlsx", XlsxParser),
        ("SAMPLE.PDF", PdfParser),
    ],
)
def test_registry_selects_parser(
    filename: str,
    expected_type: Type[object],
) -> None:
    parser = build_default_registry().get_parser(Path(filename))

    assert isinstance(parser, expected_type)


def test_registry_rejects_unsupported_extension() -> None:
    with pytest.raises(UnsupportedDocumentError):
        build_default_registry().get_parser(Path("sample.txt"))


def test_registry_rejects_duplicate_extension() -> None:
    with pytest.raises(DuplicateParserError):
        ParserRegistry([PdfParser(), PdfParser()])


def test_registry_lists_supported_extensions() -> None:
    assert build_default_registry().supported_extensions == {
        ".pdf",
        ".docx",
        ".pptx",
        ".xlsx",
    }
