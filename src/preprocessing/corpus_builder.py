from pathlib import Path
from typing import List

from src.ingestion.registry import ParserRegistry
from src.models.chunk import SearchChunk
from src.models.document import ElementType, ParsedDocument, SourceFormat
from src.preprocessing.config import ChunkingConfig
from src.preprocessing.paragraph_chunker import ParagraphChunker
from src.preprocessing.slide_chunker import SlideChunker
from src.preprocessing.spreadsheet_chunker import SpreadsheetChunker
from src.preprocessing.table_chunker import TableChunker


class CorpusBuilder:
    def __init__(self, registry: ParserRegistry, config: ChunkingConfig = ChunkingConfig()) -> None:
        self.registry = registry
        self.paragraph_chunker = ParagraphChunker(config)
        self.table_chunker = TableChunker(config)
        self.slide_chunker = SlideChunker(config)
        self.spreadsheet_chunker = SpreadsheetChunker(config)

    def build_document(self, path: Path, source_root: Path) -> List[SearchChunk]:
        document = self.registry.get_parser(path).parse(path, source_root)
        if document.source_format == SourceFormat.PPTX:
            return self.slide_chunker.chunk(document)
        if document.source_format == SourceFormat.XLSX:
            return self.spreadsheet_chunker.chunk(document)
        return self._build_ordered_document(document)

    def _build_ordered_document(self, document: ParsedDocument) -> List[SearchChunk]:
        chunks, paragraphs = [], []
        for element in document.elements:
            if element.kind == ElementType.TABLE:
                heading_only = paragraphs and all(
                    item.kind in {ElementType.TITLE, ElementType.HEADING}
                    for item in paragraphs
                )
                if heading_only:
                    section = "\n".join(item.text or "" for item in paragraphs).strip()
                    chunks.extend(self.table_chunker.chunk_element(document, element, section, paragraphs))
                    paragraphs = []
                else:
                    chunks.extend(self.paragraph_chunker.chunk_elements(document, paragraphs)); paragraphs = []
                    chunks.extend(self.table_chunker.chunk_element(document, element))
            else:
                paragraphs.append(element)
        chunks.extend(self.paragraph_chunker.chunk_elements(document, paragraphs))
        return chunks
