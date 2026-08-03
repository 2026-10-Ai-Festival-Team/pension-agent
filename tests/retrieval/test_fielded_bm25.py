from src.models.chunk import ChunkLocator, ChunkType, SearchChunk
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.fielded_bm25_index import TableRowKeyIndex
from src.retrieval.fielded_bm25_retriever import FieldedBm25Retriever
from src.retrieval.tokenizer import SimpleKoreanTokenizer


def make_chunk(identifier, kind, text):
    return SearchChunk(chunk_id=identifier, source_id=identifier, source_path=f"{identifier}.pdf", source_format="pdf", document_type="pension_guide", chunk_type=kind, text=text, locator=ChunkLocator(page_start=1, page_end=1), element_ids=[identifier])


def test_zero_weight_matches_base_bm25_order():
    chunks=[make_chunk("table",ChunkType.TABLE,"구분 | 내용\n세금납부시점 | 연금 수령시"),make_chunk("text",ChunkType.PARAGRAPH_GROUP,"연금 수령 안내"),make_chunk("other",ChunkType.PARAGRAPH_GROUP,"다른 안내")]
    token=SimpleKoreanTokenizer(); base=Bm25Index.build(chunks,token); field=TableRowKeyIndex.build(chunks,token)
    result=FieldedBm25Retriever(base,field).search("세금납부시점",row_key_weight=0).results
    assert result[0].chunk_id == "table"


def test_non_table_row_key_score_is_zero():
    chunks=[make_chunk("text",ChunkType.PARAGRAPH_GROUP,"일반 설명")]
    assert TableRowKeyIndex.build(chunks,SimpleKoreanTokenizer()).tokens == [[]]
