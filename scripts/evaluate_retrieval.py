"""Measure the frozen Simple/Kiwi BM25 retrieval baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.retrieval_dataset import load_dataset_metadata, load_questions
from src.evaluation.retrieval_evaluator import (
    evaluate_retriever,
    load_saved_retriever,
    sha256_file,
    summarize_latency,
    summarize_results,
)
from src.evaluation.retrieval_report import render_report
from src.models.chunk import SearchChunk
from src.retrieval.tokenizer import KiwiKoreanTokenizer, SimpleKoreanTokenizer


def load_chunks(path: Path) -> list[SearchChunk]:
    return [SearchChunk.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--dataset-meta", type=Path, default=Path("evaluation/retrieval_dataset_meta.json"))
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    parser.add_argument("--simple-index", type=Path, required=True)
    parser.add_argument("--kiwi-index", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--simple-output", type=Path, required=True)
    parser.add_argument("--kiwi-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    metadata = load_dataset_metadata(args.dataset_meta)
    corpus_sha256 = sha256_file(args.corpus)
    if metadata["corpus_sha256"] != corpus_sha256:
        raise RuntimeError("평가셋과 현재 Corpus의 SHA-256이 일치하지 않습니다.")

    chunks = load_chunks(args.corpus)
    questions = load_questions(args.questions)
    retrievers = {
        "simple": load_saved_retriever(args.simple_index, chunks, SimpleKoreanTokenizer(), corpus_sha256),
        "kiwi": load_saved_retriever(args.kiwi_index, chunks, KiwiKoreanTokenizer(), corpus_sha256),
    }
    results = {name: evaluate_retriever(questions, retriever, args.top_k) for name, retriever in retrievers.items()}
    write_jsonl(args.simple_output, results["simple"])
    write_jsonl(args.kiwi_output, results["kiwi"])

    summaries = {
        name: {
            "overall": summarize_results(rows),
            "dev": summarize_results(rows, "dev"),
            "test": summarize_results(rows, "test"),
        }
        for name, rows in results.items()
    }
    report = render_report(
        corpus_sha256=corpus_sha256,
        corpus_chunk_count=len(chunks),
        question_count=len(questions),
        answerable_count=sum(question.answerable for question in questions),
        unsupported_count=sum(not question.answerable for question in questions),
        all_evidence_count=sum(question.evidence_requirement == "all" for question in questions),
        results_by_tokenizer=results,
        summaries=summaries,
        latencies={name: summarize_latency(rows) for name, rows in results.items()},
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"Simple 결과: {args.simple_output}")
    print(f"Kiwi 결과: {args.kiwi_output}")
    print(f"보고서: {args.report}")


if __name__ == "__main__":
    main()
