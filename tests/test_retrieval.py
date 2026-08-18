from src.retrieval.bm25_retriever import BM25Retriever
from src.schemas.models import DocumentChunk


def chunks():
    return [
        DocumentChunk(chunk_id="C1", document_id="D1", file_name="a.txt", page=1, topic="tax", text="연금저축 세액공제 안내"),
        DocumentChunk(chunk_id="C2", document_id="D2", file_name="b.txt", page=2, topic="product", text="상품 위험등급과 총보수 안내"),
    ]


def test_retrieval_preserves_metadata_and_top_k():
    results = BM25Retriever(chunks()).retrieve("연금저축 세액공제", top_k=1)
    assert len(results) == 1
    assert results[0].document_id == "D1"
    assert results[0].page == 1


def test_empty_query_and_large_top_k():
    retriever = BM25Retriever(chunks())
    assert retriever.retrieve("", top_k=5) == []
    assert len(retriever.retrieve("안내", top_k=10)) == 2
