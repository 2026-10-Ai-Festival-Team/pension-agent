from collections import defaultdict
from typing import Dict, List

from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.models.document import ElementType, ParsedDocument
from src.preprocessing.common import collect_element_ids, join_non_empty, make_chunk_id
from src.preprocessing.config import ChunkingConfig
from src.preprocessing.table_chunker import TableChunker


class SlideChunker:
    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config
        self.table_chunker = TableChunker(config)

    def chunk(self, document: ParsedDocument) -> List[SearchChunk]:
        slides: Dict[int, List] = defaultdict(list)
        for element in document.elements:
            if element.locator.slide is not None:
                slides[element.locator.slide].append(element)
        chunks = []
        for slide, elements in sorted(slides.items()):
            buffer = []
            def flush() -> None:
                nonlocal buffer
                text = join_non_empty(item.text for item in buffer)
                if text:
                    ids = collect_element_ids(buffer)
                    chunks.append(SearchChunk(chunk_id=make_chunk_id(document.source_id, ChunkType.SLIDE, ids, f"slide-{slide}-{len(chunks)}"), source_id=document.source_id, source_path=document.relative_path, source_format=document.source_format.value, document_type=document.document_type.value, source_type=document.source_type, authority_level=document.authority_level, as_of_date=document.as_of_date or document.effective_date, title=document.title, section=None, chunk_type=ChunkType.SLIDE, text=text, locator=ChunkLocator(slide_start=slide, slide_end=slide), product_codes=document.product_codes, date_candidates=document.date_candidates, element_ids=ids, metadata={"character_count": len(text)}))
                buffer = []
            for element in elements:
                if element.kind == ElementType.TABLE:
                    flush(); chunks.extend(self.table_chunker.chunk_element(document, element)); continue
                if buffer and len(join_non_empty(item.text for item in buffer)) + len(element.text or "") > self.config.max_chars:
                    flush()
                buffer.append(element)
            flush()
        return chunks
