"""Markdown rendering for frozen BM25 retrieval baseline results."""

from __future__ import annotations

from typing import Any


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def result_row(split: str, tokenizer: str, summary: dict[str, Any]) -> str:
    return "| {} | {} | {} | {} | {} | {} | {} |".format(
        split,
        tokenizer,
        percent(summary["direct_hit_at_1"]),
        percent(summary["direct_hit_at_3"]),
        percent(summary["direct_hit_at_5"]),
        percent(summary["direct_hit_at_10"]),
        f"{summary['direct_mrr']:.3f}",
    )


def failure_type(row: dict[str, Any]) -> str:
    """Classify the initial baseline failure without modifying retrieval behavior."""
    first_direct_rank = row["first_direct_rank"]
    if first_direct_rank is not None:
        return "title_section_weight (직접 근거가 Top-5 밖)"
    if row["category"] in {"product_search", "product_code", "product_risk_fee"}:
        return "repetitive_document_noise (상품 문서 내 비관련 요소 우선)"
    return "query_document_vocabulary_gap (질의 표현과 근거 어휘 차이)"


def render_report(
    corpus_sha256: str,
    corpus_chunk_count: int,
    question_count: int,
    answerable_count: int,
    unsupported_count: int,
    all_evidence_count: int,
    results_by_tokenizer: dict[str, list[dict[str, Any]]],
    summaries: dict[str, dict[str, dict[str, Any]]],
    latencies: dict[str, dict[str, float]],
) -> str:
    lines = [
        "# BM25 검색 기준선 평가",
        "",
        "## 데이터셋",
        "",
        f"- 질문: {question_count}개",
        f"- 답변 가능: {answerable_count}개",
        f"- 답변 불가: {unsupported_count}개",
        "- 개발/테스트: 30개 / 10개",
        f"- 모든 핵심 근거가 필요한 질문: {all_evidence_count}개",
        f"- Corpus 청크: {corpus_chunk_count:,}개",
        f"- Corpus SHA-256: `{corpus_sha256}`",
        "- BM25: BM25Okapi (`k1=1.5`, `b=0.75`); Corpus·질문·Top-k는 동일하고 토크나이저만 다름.",
        "",
        "## 직접 답변 근거 결과",
        "",
        "| 분할 | 토크나이저 | R@1 | R@3 | R@5 | R@10 | MRR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    display_names = {"simple": "Simple", "kiwi": "Kiwi"}
    for split, label in (("overall", "전체"), ("dev", "개발"), ("test", "테스트")):
        for tokenizer in ("simple", "kiwi"):
            lines.append(result_row(label, display_names[tokenizer], summaries[tokenizer][split]))

    lines.extend(["", "## 전체 관련 근거 결과", "", "| 토크나이저 | R@1 | R@3 | R@5 | R@10 |", "|---|---:|---:|---:|---:|"])
    for tokenizer in ("simple", "kiwi"):
        summary = summaries[tokenizer]["overall"]
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                display_names[tokenizer],
                percent(summary["relevant_hit_at_1"]),
                percent(summary["relevant_hit_at_3"]),
                percent(summary["relevant_hit_at_5"]),
                percent(summary["relevant_hit_at_10"]),
            )
        )

    lines.extend(["", "## 복합 근거 질문", "", "| 질문 | 토크나이저 | All@5 | All@10 | Coverage@5 | Coverage@10 |", "|---|---|---:|---:|---:|---:|"])
    for tokenizer in ("simple", "kiwi"):
        for row in results_by_tokenizer[tokenizer]:
            if row.get("evidence_requirement") != "all":
                continue
            lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    row["question_id"],
                    display_names[tokenizer],
                    percent(row["all_evidence_at_5"]),
                    percent(row["all_evidence_at_10"]),
                    percent(row["evidence_coverage_at_5"]),
                    percent(row["evidence_coverage_at_10"]),
                )
            )

    lines.extend(["", "## 검색 시간", "", "| 토크나이저 | 평균 ms | p50 ms | p95 ms |", "|---|---:|---:|---:|"])
    for tokenizer in ("simple", "kiwi"):
        latency = latencies[tokenizer]
        lines.append(f"| {display_names[tokenizer]} | {latency['mean_ms']:.2f} | {latency['p50_ms']:.2f} | {latency['p95_ms']:.2f} |")

    lines.extend(
        [
            "",
            "## 직접 근거 실패 질의",
            "",
            "| ID | 토크나이저 | 범주 | 첫 직접 근거 순위 | 원인 |",
            "|---|---|---|---:|---|",
        ]
    )
    failures: list[str] = []
    for tokenizer in ("simple", "kiwi"):
        for row in results_by_tokenizer[tokenizer]:
            if row.get("answerable") and row["direct_hit_at_5"] == 0:
                failures.append(
                    "| {} | {} | {} | {} | {} |".format(
                        row["question_id"],
                        display_names[tokenizer],
                        row["category"],
                        row["first_direct_rank"] or ">10",
                        failure_type(row),
                    )
                )
    lines.extend(failures or ["| - | - | - | - | 없음 |"])
    return "\n".join(lines) + "\n"
