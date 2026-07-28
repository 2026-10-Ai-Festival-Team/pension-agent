"""Collect unbiased Simple/Kiwi BM25 candidates for retrieval-evaluation labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.chunk import SearchChunk
from src.models.retrieval import SearchResult
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.bm25_retriever import Bm25Retriever
from src.retrieval.tokenizer import KiwiKoreanTokenizer, SimpleKoreanTokenizer


def load_questions(path: Path) -> list[dict[str, Any]]:
    """Load JSONL question drafts without assuming that evidence is labeled."""
    questions: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        question = json.loads(line)
        if not question.get("question_id") or not question.get("question"):
            raise ValueError(f"{path}:{line_number} requires question_id and question")
        questions.append(question)
    return questions


def load_chunks(path: Path) -> list[SearchChunk]:
    return [
        SearchChunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def result_summary(result: SearchResult) -> dict[str, Any]:
    return {"chunk_id": result.chunk_id, "rank": result.rank, "score": result.score}


def candidate_record(
    chunk: SearchChunk,
    simple_result: SearchResult | None,
    kiwi_result: SearchResult | None,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "simple_rank": simple_result.rank if simple_result else None,
        "simple_score": simple_result.score if simple_result else None,
        "kiwi_rank": kiwi_result.rank if kiwi_result else None,
        "kiwi_score": kiwi_result.score if kiwi_result else None,
        "source_id": chunk.source_id,
        "source_path": chunk.source_path,
        "source_format": chunk.source_format,
        "document_type": chunk.document_type,
        "title": chunk.title,
        "section": chunk.section,
        "locator": chunk.locator.model_dump(mode="json"),
        "product_codes": chunk.product_codes,
        "element_ids": chunk.element_ids,
        "text": chunk.text,
    }


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, float, str]:
    ranks = [rank for rank in (candidate["simple_rank"], candidate["kiwi_rank"]) if rank]
    scores = [score for score in (candidate["simple_score"], candidate["kiwi_score"]) if score is not None]
    appears_in_both = candidate["simple_rank"] is not None and candidate["kiwi_rank"] is not None
    return (0 if appears_in_both else 1, min(ranks), -max(scores), candidate["chunk_id"])


def collect_candidates(
    chunks: list[SearchChunk], questions: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    """Return ranked union candidates, preserving each tokenizer's result metadata."""
    retrievers = {
        "simple": Bm25Retriever(Bm25Index.build(chunks, SimpleKoreanTokenizer())),
        "kiwi": Bm25Retriever(Bm25Index.build(chunks, KiwiKoreanTokenizer())),
    }
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    rows: list[dict[str, Any]] = []

    for question in questions:
        responses = {
            name: retriever.search(question["question"], top_k=top_k)
            for name, retriever in retrievers.items()
        }
        results_by_tokenizer = {
            name: {result.chunk_id: result for result in response.results}
            for name, response in responses.items()
        }
        candidate_ids = set(results_by_tokenizer["simple"]) | set(results_by_tokenizer["kiwi"])
        candidates = [
            candidate_record(
                chunks_by_id[chunk_id],
                results_by_tokenizer["simple"].get(chunk_id),
                results_by_tokenizer["kiwi"].get(chunk_id),
            )
            for chunk_id in candidate_ids
        ]
        candidates.sort(key=candidate_sort_key)
        rows.append(
            {
                "question_id": question["question_id"],
                "question": question["question"],
                "corpus_sha256": "",
                "simple": {
                    "tokenizer": responses["simple"].tokenizer,
                    "results": [result_summary(item) for item in responses["simple"].results],
                },
                "kiwi": {
                    "tokenizer": responses["kiwi"].tokenizer,
                    "results": [result_summary(item) for item in responses["kiwi"].results],
                },
                "candidates": candidates,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.top_k < 1:
        raise ValueError("--top-k must be at least 1")

    chunks = load_chunks(args.corpus)
    corpus_sha256 = hashlib.sha256(args.corpus.read_bytes()).hexdigest()
    rows = collect_candidates(chunks, load_questions(args.questions), args.top_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for row in rows:
            row["corpus_sha256"] = corpus_sha256
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"질문 수: {len(rows)}")
    print(f"Corpus SHA-256: {corpus_sha256}")
    print(f"생성 완료: {args.output}")


if __name__ == "__main__":
    main()
