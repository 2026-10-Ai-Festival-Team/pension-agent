"""Evaluate saved BM25 indexes without changing retrieval behavior."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from src.evaluation.retrieval_dataset import RetrievalQuestion
from src.evaluation.retrieval_metrics import (
    all_evidence_at_k,
    evidence_coverage_at_k,
    first_relevant_rank,
    hit_at_k,
    reciprocal_rank,
)
from src.models.chunk import SearchChunk
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.bm25_retriever import Bm25Retriever


METRIC_KS = (1, 3, 5, 10)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_saved_retriever(
    index_path: Path,
    chunks: list[SearchChunk],
    tokenizer: Any,
    expected_corpus_sha256: str,
) -> Bm25Retriever:
    """Rebuild BM25 from saved tokens after validating metadata and chunk order."""
    metadata = json.loads((index_path / "index_meta.json").read_text(encoding="utf-8"))
    if metadata.get("corpus_sha256") != expected_corpus_sha256:
        raise RuntimeError("Corpus and retrieval indexes use different SHA-256 values.")
    if metadata.get("tokenizer") != tokenizer.name:
        raise RuntimeError(f"인덱스 토크나이저가 일치하지 않습니다: {index_path}")
    if metadata.get("chunk_count") != len(chunks):
        raise RuntimeError(f"인덱스 청크 수가 Corpus와 일치하지 않습니다: {index_path}")
    bm25_parameters = metadata.get("bm25")
    if bm25_parameters != {"algorithm": "BM25Okapi", "k1": 1.5, "b": 0.75}:
        raise RuntimeError(f"BM25 파라미터가 기준선과 일치하지 않습니다: {index_path}")

    token_rows = [
        json.loads(line)
        for line in (index_path / "tokenized_documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(token_rows) != len(chunks):
        raise RuntimeError(f"저장된 토큰 수가 Corpus와 일치하지 않습니다: {index_path}")
    if [row["chunk_id"] for row in token_rows] != [chunk.chunk_id for chunk in chunks]:
        raise RuntimeError(f"저장된 토큰 순서가 Corpus와 일치하지 않습니다: {index_path}")
    return Bm25Retriever(Bm25Index(chunks, [row["tokens"] for row in token_rows], tokenizer))


def evaluate_retriever(
    questions: list[RetrievalQuestion], retriever: Bm25Retriever, top_k: int, query_normalizer: Any = None
) -> list[dict[str, Any]]:
    if top_k < max(METRIC_KS):
        raise ValueError("top_k는 최소 10이어야 합니다.")

    rows: list[dict[str, Any]] = []
    for question in questions:
        started = time.perf_counter()
        search_kwargs = {"query_normalizer": query_normalizer} if query_normalizer is not None else {}
        response = retriever.search(question.question, top_k=top_k, **search_kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        _validate_ranked_results(response.results)
        retrieved_ids = [result.chunk_id for result in response.results]
        base = {
            "question_id": question.question_id,
            "split": question.split,
            "category": question.category,
            "tokenizer": response.tokenizer,
            "answerable": question.answerable,
            "evidence_requirement": question.evidence_requirement,
            "product_codes": question.product_codes,
            "retrieved_chunk_ids": retrieved_ids,
            "elapsed_ms": elapsed_ms,
        }
        if not question.answerable:
            rows.append(
                {
                    **base,
                    "excluded_from_ranking_metrics": True,
                    "top_score": response.results[0].score if response.results else None,
                }
            )
            continue

        direct_ids = question.direct_evidence_ids
        all_relevant_ids = question.all_relevant_ids
        row: dict[str, Any] = {
            **base,
            "excluded_from_ranking_metrics": False,
            "direct_evidence_ids": sorted(direct_ids),
            "all_relevant_ids": sorted(all_relevant_ids),
            "first_direct_rank": first_relevant_rank(retrieved_ids, direct_ids),
            "first_relevant_rank": first_relevant_rank(retrieved_ids, all_relevant_ids),
            "reciprocal_rank": reciprocal_rank(retrieved_ids, direct_ids),
            "relevant_reciprocal_rank": reciprocal_rank(retrieved_ids, all_relevant_ids),
        }
        for k in METRIC_KS:
            row[f"direct_hit_at_{k}"] = hit_at_k(retrieved_ids, direct_ids, k)
            row[f"relevant_hit_at_{k}"] = hit_at_k(retrieved_ids, all_relevant_ids, k)
        if question.evidence_requirement == "all":
            row["all_evidence_at_5"] = all_evidence_at_k(retrieved_ids, direct_ids, 5)
            row["all_evidence_at_10"] = all_evidence_at_k(retrieved_ids, direct_ids, 10)
            row["evidence_coverage_at_5"] = evidence_coverage_at_k(retrieved_ids, direct_ids, 5)
            row["evidence_coverage_at_10"] = evidence_coverage_at_k(retrieved_ids, direct_ids, 10)
        else:
            row["all_evidence_at_5"] = None
            row["all_evidence_at_10"] = None
            row["evidence_coverage_at_5"] = None
            row["evidence_coverage_at_10"] = None
        rows.append(row)
    return rows


def _validate_ranked_results(results: list[Any]) -> None:
    """Fail fast if a retriever violates the ranking contract under evaluation."""
    ranks = [result.rank for result in results]
    if ranks != list(range(1, len(results) + 1)):
        raise RuntimeError("검색 결과 순위가 1부터 연속적으로 정렬되어 있지 않습니다.")
    scores = [result.score for result in results]
    if any(previous < current for previous, current in zip(scores, scores[1:])):
        raise RuntimeError("검색 결과 점수가 내림차순으로 정렬되어 있지 않습니다.")


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentage
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summarize_results(rows: list[dict[str, Any]], split: str | None = None) -> dict[str, Any]:
    selected = [row for row in rows if row["answerable"] and (split is None or row["split"] == split)]
    if not selected:
        return {"question_count": 0}
    summary: dict[str, Any] = {"question_count": len(selected)}
    for prefix in ("direct", "relevant"):
        for k in METRIC_KS:
            summary[f"{prefix}_hit_at_{k}"] = sum(row[f"{prefix}_hit_at_{k}"] for row in selected) / len(selected)
    summary["direct_mrr"] = sum(row["reciprocal_rank"] for row in selected) / len(selected)
    summary["relevant_mrr"] = sum(row["relevant_reciprocal_rank"] for row in selected) / len(selected)
    return summary


def summarize_latency(rows: list[dict[str, Any]]) -> dict[str, float]:
    values = [row["elapsed_ms"] for row in rows]
    return {
        "mean_ms": sum(values) / len(values) if values else 0.0,
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
    }


def summarize_composite_evidence(rows: list[dict[str, Any]]) -> dict[str, float]:
    composite_rows = [row for row in rows if row.get("evidence_requirement") == "all" and row["answerable"]]
    if not composite_rows:
        return {"question_count": 0, "all_evidence_at_5": 0.0, "all_evidence_at_10": 0.0}
    return {
        "question_count": len(composite_rows),
        "all_evidence_at_5": sum(row["all_evidence_at_5"] for row in composite_rows) / len(composite_rows),
        "all_evidence_at_10": sum(row["all_evidence_at_10"] for row in composite_rows) / len(composite_rows),
    }
