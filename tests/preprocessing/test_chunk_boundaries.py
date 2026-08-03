from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.models.document import DocumentElement, ElementType, Locator, TableData
from scripts.analyze_broad_chunks import classify_broad_chunk


def chunk(chunk_type: ChunkType, text: str) -> SearchChunk:
    return SearchChunk(
        chunk_id="chunk",
        source_id="source",
        source_path="source.pdf",
        source_format="pdf",
        document_type="pension_guide",
        chunk_type=chunk_type,
        text=text,
        locator=ChunkLocator(page_start=1, page_end=1),
        element_ids=["element"],
    )


def test_paragraph_with_multiple_topic_markers_is_mixed():
    element = DocumentElement(element_id="element", order=0, kind=ElementType.PARAGRAPH, locator=Locator(page=1), text="○ 첫 주제\n○ 둘째 주제")

    assert classify_broad_chunk(chunk(ChunkType.PARAGRAPH_GROUP, element.text), [element]) == "A_mixed_topics"


def test_table_with_multiple_data_rows_is_mixed():
    element = DocumentElement(
        element_id="element",
        order=0,
        kind=ElementType.TABLE,
        locator=Locator(page=1),
        table=TableData(rows=[["헤더"], ["행 1"], ["행 2"]]),
    )

    assert classify_broad_chunk(chunk(ChunkType.TABLE, "헤더\n행 1\n행 2"), [element]) == "A_mixed_topics"
