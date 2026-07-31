import json

import pytest

from src.evaluation.retrieval_dataset import Evidence, RetrievalQuestion
from src.evaluation.retrieval_evaluator import (
    evaluate_retriever,
    load_saved_retriever,
    summarize_results,
)
from src.retrieval.tokenizer import SimpleKoreanTokenizer
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult


class FakeRetriever:
    def search(self, query, top_k):
        results = [
            SearchResult(
                rank=1,
                chunk_id="chunk-2",
                score=1.0,
                text="text",
                source_id="source",
                source_path="source.pdf",
                source_format="pdf",
                document_type="pension_guide",
                locator=ChunkLocator(page_start=1, page_end=1),
            ),
            SearchResult(
                rank=2,
                chunk_id="chunk-1",
                score=0.5,
                text="text",
                source_id="source",
                source_path="source.pdf",
                source_format="pdf",
                document_type="pension_guide",
                locator=ChunkLocator(page_start=1, page_end=1),
            ),
        ]
        return SearchResponse(query=query, tokenizer="fake", total_candidates=2, results=results)


def question(question_id, answerable=True, requirement="any"):
    evidence = [
        Evidence(chunk_id="chunk-1", source_id="source", relevance=2, locator={}),
        Evidence(chunk_id="chunk-2", source_id="source", relevance=2, locator={}),
    ] if answerable else []
    return RetrievalQuestion(
        question_id=question_id,
        split="dev",
        question="질문",
        category="test",
        answerable=answerable,
        requires_ocr=False,
        product_codes=[],
        relevant_chunks=evidence,
        relevant_source_ids=["source"] if answerable else [],
        required_terms=["근거"] if answerable else [],
        evidence_requirement=requirement,
        notes=[],
    )


def test_evaluator_records_direct_and_composite_metrics():
    rows = evaluate_retriever([question("R-1", requirement="all")], FakeRetriever(), top_k=10)

    assert rows[0]["first_direct_rank"] == 1
    assert rows[0]["direct_hit_at_1"] == 1.0
    assert rows[0]["all_evidence_at_5"] == 1.0
    assert rows[0]["evidence_coverage_at_10"] == 1.0


def test_unsupported_question_is_excluded_from_ranking_summary():
    rows = evaluate_retriever([question("R-1"), question("R-2", answerable=False)], FakeRetriever(), top_k=10)

    assert rows[1]["excluded_from_ranking_metrics"] is True
    assert summarize_results(rows)["question_count"] == 1


def test_evaluator_rejects_results_with_ascending_scores():
    class InvalidRetriever(FakeRetriever):
        def search(self, query, top_k):
            response = super().search(query, top_k)
            response.results[1].score = 2.0
            return response

    with pytest.raises(RuntimeError, match="점수"):
        evaluate_retriever([question("R-1")], InvalidRetriever(), top_k=10)


def test_evaluator_metrics_are_reproducible_except_for_elapsed_time():
    first = evaluate_retriever([question("R-1")], FakeRetriever(), top_k=10)[0]
    second = evaluate_retriever([question("R-1")], FakeRetriever(), top_k=10)[0]

    first.pop("elapsed_ms")
    second.pop("elapsed_ms")
    assert first == second


def test_saved_retriever_rejects_wrong_corpus_hash(tmp_path):
    (tmp_path / "index_meta.json").write_text(
        json.dumps({"corpus_sha256": "wrong"}), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="SHA-256"):
        load_saved_retriever(tmp_path, [], SimpleKoreanTokenizer(), "expected")
