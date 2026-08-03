from typing import List, Optional

from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.models.document import DocumentElement, DocumentType, ParsedDocument, SourceFormat
from src.preprocessing.common import make_chunk_id
from src.preprocessing.config import ChunkingConfig


class TableChunker:
    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config

    def chunk_element(self, document: ParsedDocument, element: DocumentElement, section: Optional[str] = None, prefix_elements: Optional[List[DocumentElement]] = None) -> List[SearchChunk]:
        if element.table is None:
            return []
        rows = [row for row in element.table.rows if any(cell for cell in row)]
        if not rows:
            return []
        header, data_rows = rows[0], rows[1:]
        rows_per_chunk = self._rows_per_chunk(document, header, data_rows)
        groups = [data_rows[index:index + rows_per_chunk] for index in range(0, len(data_rows), rows_per_chunk)] or [[]]
        chunks = []
        prefix_elements = prefix_elements or []
        element_ids = [item.element_id for item in prefix_elements] + [element.element_id]
        for index, group in enumerate(groups):
            row_start = 2 + index * rows_per_chunk
            row_end = row_start + len(group) - 1
            text = self.render_rows([header] + group)
            context = section or (document.title if rows_per_chunk != self.config.table_rows_per_chunk else None)
            if context:
                text = f"{context}\n{text}"
            chunks.append(SearchChunk(
                chunk_id=make_chunk_id(document.source_id, ChunkType.TABLE, element_ids, f"rows-{row_start}-{row_end}"),
                source_id=document.source_id, source_path=document.relative_path, source_format=document.source_format.value,
                document_type=document.document_type.value, title=document.title, section=section, chunk_type=ChunkType.TABLE, text=text,
                locator=ChunkLocator(page_start=element.locator.page, page_end=element.locator.page, slide_start=element.locator.slide, slide_end=element.locator.slide, sheet=element.locator.sheet, cell_range=element.locator.cell_range),
                product_codes=document.product_codes, date_candidates=document.date_candidates, element_ids=element_ids,
                metadata={"header_row_count": 1, "data_row_start": row_start, "data_row_end": row_end, "merged_ranges": element.table.merged_ranges},
            ))
        return chunks

    def _rows_per_chunk(self, document: ParsedDocument, header: List[Optional[str]], data_rows: List[List[Optional[str]]]) -> int:
        full_text_length = len(self.render_rows([header] + data_rows))
        if (
            document.source_format in {SourceFormat.PDF, SourceFormat.DOCX}
            and document.document_type == DocumentType.PENSION_GUIDE
            and 3 <= len(data_rows) <= self.config.refined_table_max_data_rows
            and full_text_length >= self.config.refined_table_min_chars
        ):
            return self.config.refined_table_rows_per_chunk
        return self.config.table_rows_per_chunk

    @staticmethod
    def render_rows(rows: List[List[Optional[str]]]) -> str:
        return "\n".join(" | ".join((cell or "").strip() for cell in row).rstrip() for row in rows).strip()
