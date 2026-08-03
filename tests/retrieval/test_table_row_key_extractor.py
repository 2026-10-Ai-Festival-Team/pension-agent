from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.retrieval.table_row_key_extractor import row_keys


def chunk(kind=ChunkType.TABLE, text="구분 | 내용\n연금 수령 | 분할 지급\n일시금 수령 | 일괄 지급"):
    return SearchChunk(chunk_id="c", source_id="s", source_path="x.pdf", source_format="pdf", document_type="pension_guide", chunk_type=kind, text=text, locator=ChunkLocator(page_start=1, page_end=1), element_ids=["e"])


def test_row_keys_exclude_header_and_keep_first_data_cells():
    assert row_keys(chunk()) == ["연금 수령", "일시금 수령"]


def test_non_table_chunk_has_no_row_key():
    assert row_keys(chunk(ChunkType.PARAGRAPH_GROUP)) == []
