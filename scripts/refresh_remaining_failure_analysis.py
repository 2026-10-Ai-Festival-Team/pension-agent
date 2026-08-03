"""Reassess dev-only BM25 failures and simulate source-diversity caps."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_dataset import load_dataset_metadata, load_questions
from src.evaluation.retrieval_evaluator import load_saved_retriever, sha256_file
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
from src.retrieval.tokenizer import SimpleKoreanTokenizer


def cap_results(results, cap: int | None):
    if cap is None:
        return results
    kept, counts = [], Counter()
    for result in results:
        if counts[result.source_id] < cap:
            kept.append(result)
            counts[result.source_id] += 1
    return kept


def rank_of(results, gold_ids: set[str]) -> int | None:
    return next((index for index, result in enumerate(results, 1) if result.chunk_id in gold_ids), None)


def classify(question, gold_chunks, uncapped_rank, capped_rank) -> str:
    if capped_rank and (uncapped_rank is None or capped_rank < uncapped_rank):
        return "repetitive_document_noise"
    if any(chunk.chunk_type.value == "table" for chunk in gold_chunks):
        return "table_row_term_missing"
    return "query_document_vocabulary_gap" if uncapped_rank is None else "gold_competitor_mismatch"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--dataset-meta", type=Path, default=Path("evaluation/retrieval_dataset_meta.json"))
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    parser.add_argument("--simple-index", type=Path, default=Path("data/indexes/bm25/simple"))
    parser.add_argument("--output", type=Path, default=Path("data/diagnostics/retrieval_failure_analysis_current.csv"))
    parser.add_argument("--simulation-output", type=Path, default=Path("data/diagnostics/source_diversity_simulation.csv"))
    parser.add_argument("--report", type=Path, default=Path("docs/retrieval_failure_analysis_current.md"))
    args = parser.parse_args()

    corpus_sha = sha256_file(args.corpus)
    if load_dataset_metadata(args.dataset_meta)["corpus_sha256"] != corpus_sha:
        raise RuntimeError("평가셋과 Corpus SHA-256이 일치하지 않습니다.")
    chunks = load_chunks(args.corpus)
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    tokenizer = SimpleKoreanTokenizer()
    retriever = load_saved_retriever(args.simple_index, chunks, tokenizer, corpus_sha)
    normalizer = build_default_pension_query_normalizer()
    failure_rows, simulation_rows, all_rank_rows = [], [], []
    for question in load_questions(args.questions):
        if question.split != "dev" or not question.answerable:
            continue
        results = retriever.search(question.question, top_k=100, query_normalizer=normalizer).results
        gold_ids = question.direct_evidence_ids
        ranks = {cap: rank_of(cap_results(results, cap), gold_ids) for cap in (None, 3, 2)}
        all_rank_rows.append(ranks)
        if ranks[None] is not None and ranks[None] <= 5:
            continue
        gold_chunks = [by_id[chunk_id] for chunk_id in gold_ids]
        gold_tokens = set(tokenizer.tokenize("\n".join(chunk.text for chunk in gold_chunks)))
        query_tokens = tokenizer.tokenize(question.question)
        top10 = results[:10]
        source_counts = Counter(result.source_id for result in top10)
        top_source, top_source_count = source_counts.most_common(1)[0]
        failure_rows.append({
            "question_id": question.question_id, "question": question.question,
            "failure_band": "top10_failure" if ranks[None] is None or ranks[None] > 10 else "top5_only_failure",
            "failure_type": classify(question, gold_chunks, ranks[None], ranks[2]),
            "rank_no_cap": ranks[None] or ">100", "rank_cap_3": ranks[3] or ">100", "rank_cap_2": ranks[2] or ">100",
            "unique_sources_top10": len(source_counts), "max_source_id": top_source, "max_source_chunks": top_source_count,
            "gold_source_chunks_top10": sum(result.source_id in {chunk.source_id for chunk in gold_chunks} for result in top10),
            "max_source_ratio_top10": round(top_source_count / 10, 3),
            "query_tokens": json.dumps(query_tokens, ensure_ascii=False),
            "gold_tokens": json.dumps(sorted(gold_tokens), ensure_ascii=False),
            "common_tokens": json.dumps(sorted(set(query_tokens) & gold_tokens), ensure_ascii=False),
            "query_only_tokens": json.dumps(sorted(set(query_tokens) - gold_tokens), ensure_ascii=False),
        })
        for cap, label in ((None, "No cap"), (3, "Max 3/source"), (2, "Max 2/source")):
            simulation_rows.append({"question_id": question.question_id, "variant": label, "gold_rank": ranks[cap] or ">100"})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    for path, rows in ((args.output, failure_rows), (args.simulation_output, simulation_rows)):
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    counts = Counter(row["failure_type"] for row in failure_rows)
    bands = {band: Counter(row["failure_type"] for row in failure_rows if row["failure_band"] == band) for band in ("top5_only_failure", "top10_failure")}
    lines = ["# 현재 BM25 dev 실패 재분석", "", "- 기준: 원본 Corpus 23,421청크, Simple, `pension-v1`", "- test 질문과 결과는 사용하지 않았다.", "", "## 실패 분포", "", "| Failure type | Top-5 실패·Top-10 성공 | Direct Top-10 실패 |", "|---|---:|---:|"]
    for kind in ("repetitive_document_noise", "query_document_vocabulary_gap", "table_row_term_missing", "gold_competitor_mismatch", "other"):
        lines.append(f"| `{kind}` | {bands['top5_only_failure'][kind]} | {bands['top10_failure'][kind]} |")
    lines += ["", "## Source cap 시뮬레이션", "", "Top-100을 점수 순서로 유지한 뒤 source별 반환 수만 제한했다. 이는 검색 코드 변경이 아닌 오프라인 가정이다.", "", "| Variant | Dev R@5 | Dev R@10 | Improved | Regressed |", "|---|---:|---:|---:|---:|"]
    for cap, label in ((None, "No cap"), (3, "Max 3/source"), (2, "Max 2/source")):
        key = {None: "rank_no_cap", 3: "rank_cap_3", 2: "rank_cap_2"}[cap]
        rank_key = {"rank_no_cap": None, "rank_cap_3": 3, "rank_cap_2": 2}[key]
        ranks = [row[rank_key] or 101 for row in all_rank_rows]
        base = [row[None] or 101 for row in all_rank_rows]
        lines.append(f"| {label} | {sum(rank <= 5 for rank in ranks)}/{len(all_rank_rows)} | {sum(rank <= 10 for rank in ranks)}/{len(all_rank_rows)} | {sum(rank < before for rank, before in zip(ranks, base))} | {sum(rank > before for rank, before in zip(ranks, base))} |")
    lines += ["", "상세 토큰·source 점유·질문별 cap 순위는 Git 제외 CSV에 저장했다."]
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"분석 질문: {len(failure_rows)}개")


if __name__ == "__main__":
    main()
