from typing import List, Optional

from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.models.document import DocumentElement, ParsedDocument
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
        groups = [data_rows[index:index + self.config.table_rows_per_chunk] for index in range(0, len(data_rows), self.config.table_rows_per_chunk)] or [[]]
        chunks = []
        prefix_elements = prefix_elements or []
        element_ids = [item.element_id for item in prefix_elements] + [element.element_id]
        for index, group in enumerate(groups):
            row_start = 2 + index * self.config.table_rows_per_chunk
            row_end = row_start + len(group) - 1
            text = self.render_rows([header] + group)
            if section:
                text = f"{section}\n{text}"
            chunks.append(SearchChunk(
                chunk_id=make_chunk_id(document.source_id, ChunkType.TABLE, element_ids, f"rows-{row_start}-{row_end}"),
                source_id=document.source_id, source_path=document.relative_path, source_format=document.source_format.value,
                document_type=document.document_type.value, title=document.title, section=section, chunk_type=ChunkType.TABLE, text=text,
                source_type=document.source_type, authority_level=document.authority_level,
                as_of_date=document.as_of_date or document.effective_date,
                locator=ChunkLocator(page_start=element.locator.page, page_end=element.locator.page, slide_start=element.locator.slide, slide_end=element.locator.slide, sheet=element.locator.sheet, cell_range=element.locator.cell_range),
                product_codes=document.product_codes, date_candidates=document.date_candidates, element_ids=element_ids,
                metadata={"header_row_count": 1, "data_row_start": row_start, "data_row_end": row_end, "merged_ranges": element.table.merged_ranges},
            ))
        return chunks

    @staticmethod
    def render_rows(rows: List[List[Optional[str]]]) -> str:
        return "\n".join(" | ".join((cell or "").strip() for cell in row).rstrip() for row in rows).strip()
