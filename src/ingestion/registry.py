"""Parser lookup by file extension."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Set

from src.ingestion.base import DocumentParser
from src.ingestion.docx_parser import DocxParser
from src.ingestion.pdf_parser import PdfParser
from src.ingestion.pptx_parser import PptxParser
from src.ingestion.xlsx_parser import XlsxParser


class UnsupportedDocumentError(ValueError):
    """Raised when no parser supports a document extension."""


class DuplicateParserError(ValueError):
    """Raised when more than one parser claims the same extension."""


class ParserRegistry:
    """Map normalized file extensions to document parsers."""

    def __init__(self, parsers: Iterable[DocumentParser]) -> None:
        self._parsers: Dict[str, DocumentParser] = {}

        for parser in parsers:
            self.register(parser)

    def register(self, parser: DocumentParser) -> None:
        for extension in parser.supported_extensions:
            normalized_extension = extension.lower()
            if not normalized_extension.startswith("."):
                normalized_extension = f".{normalized_extension}"

            if normalized_extension in self._parsers:
                raise DuplicateParserError(
                    "Parser already registered for extension: "
                    f"{normalized_extension}"
                )

            self._parsers[normalized_extension] = parser

    def get_parser(self, path: Path) -> DocumentParser:
        extension = path.suffix.lower()
        parser = self._parsers.get(extension)
        if parser is None:
            raise UnsupportedDocumentError(
                f"Unsupported document extension: {extension}"
            )
        return parser

    @property
    def supported_extensions(self) -> Set[str]:
        return set(self._parsers.keys())


def build_default_registry() -> ParserRegistry:
    """Return the registry for every source format in the initial corpus."""
    return ParserRegistry(
        parsers=[PdfParser(), DocxParser(), PptxParser(), XlsxParser()]
    )
