import re
from typing import List, Optional

from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.models.document import DocumentElement, ElementType, ParsedDocument, SourceFormat
from src.preprocessing.common import collect_element_ids, join_non_empty, make_chunk_id
from src.preprocessing.config import ChunkingConfig


class ParagraphChunker:
    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config

    def chunk_elements(self, document: ParsedDocument, elements: List[DocumentElement]) -> List[SearchChunk]:
        chunks: List[SearchChunk] = []
        buffer: List[DocumentElement] = []
        section: Optional[str] = None

        def flush() -> None:
            nonlocal buffer
            text = join_non_empty(element.text for element in buffer)
            if text:
                ids = collect_element_ids(buffer)
                pages = [item.locator.page for item in buffer if item.locator.page is not None]
                chunks.append(SearchChunk(
                    chunk_id=make_chunk_id(document.source_id, ChunkType.PARAGRAPH_GROUP, ids, f"segment-{len(chunks)}"),
                    source_id=document.source_id, source_path=document.relative_path,
                    source_format=document.source_format.value, document_type=document.document_type.value,
                    title=document.title, section=section, chunk_type=ChunkType.PARAGRAPH_GROUP, text=text,
                    locator=ChunkLocator(page_start=min(pages) if pages else None, page_end=max(pages) if pages else None),
                    product_codes=document.product_codes, date_candidates=document.date_candidates, element_ids=ids,
                    metadata={"character_count": len(text), "element_count": len(buffer)},
                ))
            buffer = []

        for element in elements:
            if not element.text:
                continue
            if element.kind in {ElementType.TITLE, ElementType.HEADING}:
                flush()
                section = element.text
            elif buffer and self._is_topic_start(document, element):
                flush()
            if buffer and self._must_split(document, buffer, element):
                flush()
            buffer.append(element)
            if len(join_non_empty(item.text for item in buffer)) >= self.config.target_chars:
                flush()
        flush()
        return chunks

    def _must_split(self, document: ParsedDocument, buffer: List[DocumentElement], next_element: DocumentElement) -> bool:
        projected = len(join_non_empty(item.text for item in buffer)) + 1 + len(next_element.text or "")
        if projected > self.config.max_chars:
            return True
        return document.source_format == SourceFormat.PDF and buffer[-1].locator.page != next_element.locator.page

    @staticmethod
    def _is_topic_start(document: ParsedDocument, element: DocumentElement) -> bool:
        """Detect PDF question/subtopic blocks without splitting ordinary list items."""
        return document.source_format == SourceFormat.PDF and bool(
            re.match(r"^\s*[○●■]\s*\S", element.text or "")
        )
