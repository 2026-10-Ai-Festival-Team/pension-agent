"""Measure frozen BM25 baselines or a dev-only query-normalization experiment."""

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
    summarize_composite_evidence,
    summarize_results,
)
from src.evaluation.query_normalization_report import render_query_normalization_report
from src.evaluation.retrieval_report import render_report
from src.models.chunk import SearchChunk
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
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
    parser.add_argument("--simple-index", type=Path, default=Path("data/indexes/bm25/simple"))
    parser.add_argument("--kiwi-index", type=Path, default=Path("data/indexes/bm25/kiwi"))
    parser.add_argument("--tokenizer", choices=("simple", "kiwi"))
    parser.add_argument("--query-normalization", choices=("none", "pension-v1"), default="none")
    parser.add_argument("--split", choices=("all", "dev", "test"), default="all")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--simple-output", type=Path, default=Path("data/diagnostics/retrieval_eval_simple.jsonl"))
    parser.add_argument("--kiwi-output", type=Path, default=Path("data/diagnostics/retrieval_eval_kiwi.jsonl"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path, default=Path("docs/retrieval_evaluation_report.md"))
    args = parser.parse_args()

    metadata = load_dataset_metadata(args.dataset_meta)
    corpus_sha256 = sha256_file(args.corpus)
    if metadata["corpus_sha256"] != corpus_sha256:
        raise RuntimeError("평가셋과 현재 Corpus의 SHA-256이 일치하지 않습니다.")

    chunks = load_chunks(args.corpus)
    questions = load_questions(args.questions)
    if args.split != "all":
        questions = [question for question in questions if question.split == args.split]
    if not questions:
        raise ValueError("선택한 split에 평가 질문이 없습니다.")
    if args.tokenizer:
        index_path, tokenizer = (
            (args.simple_index, SimpleKoreanTokenizer())
            if args.tokenizer == "simple"
            else (args.kiwi_index, KiwiKoreanTokenizer())
        )
        retriever = load_saved_retriever(index_path, chunks, tokenizer, corpus_sha256)
        _run_single_tokenizer_experiment(args, questions, retriever)
        return

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


def _run_single_tokenizer_experiment(args, questions, retriever) -> None:
    if args.output is None:
        raise ValueError("--tokenizer를 지정할 때는 --output이 필요합니다.")
    normalizer = build_default_pension_query_normalizer() if args.query_normalization == "pension-v1" else None
    evaluated_rows = evaluate_retriever(questions, retriever, args.top_k, query_normalizer=normalizer)
    write_jsonl(args.output, evaluated_rows)

    if args.query_normalization == "pension-v1":
        baseline_rows = evaluate_retriever(questions, retriever, args.top_k)
        report = render_query_normalization_report(
            baseline_summary=summarize_results(baseline_rows),
            normalized_summary=summarize_results(evaluated_rows),
            baseline_composite=summarize_composite_evidence(baseline_rows),
            normalized_composite=summarize_composite_evidence(evaluated_rows),
            baseline_latency=summarize_latency(baseline_rows),
            normalized_latency=summarize_latency(evaluated_rows),
            baseline_rows=baseline_rows,
            normalized_rows=evaluated_rows,
        )
    else:
        report = "# 단일 토크나이저 평가\n\n" + json.dumps(summarize_results(evaluated_rows), ensure_ascii=False, indent=2) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(f"{args.tokenizer} 결과: {args.output}")
    print(f"보고서: {args.report}")


if __name__ == "__main__":
    main()
