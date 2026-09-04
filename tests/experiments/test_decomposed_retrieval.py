from src.experiments.decomposed_retrieval import retrieve_by_requirement
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult


def result(rank, chunk_id):
    return SearchResult(
        rank=rank, chunk_id=chunk_id, score=float(10 - rank), text=chunk_id,
        source_id="source", source_path="guide.pdf", source_format="pdf", document_type="guide",
        locator=ChunkLocator(page_start=rank, page_end=rank), element_ids=[chunk_id],
    )


class Retriever:
    def search(self, query, top_k):
        rows = {
            "DB 운용": [result(1, "db"), result(2, "shared")],
            "DC 운용": [result(1, "dc"), result(2, "shared")],
        }[query]
        return SearchResponse(query=query, tokenizer="simple", total_candidates=len(rows), results=rows[:top_k])


def test_decomposed_retrieval_keeps_slot_results_and_deduplicates_merge():
    output = retrieve_by_requirement(Retriever(), {"DB": "DB 운용", "DC": "DC 운용"}, top_k=5)

    assert [item.chunk_id for item in output.slot_results["DB"]] == ["db", "shared"]
    assert [item.chunk_id for item in output.merged_results] == ["db", "shared", "dc"]
    assert [item.rank for item in output.merged_results] == [1, 2, 3]
