"""Report rendering for the dev-only limited query-normalization experiment."""

from __future__ import annotations

from typing import Any

from src.retrieval.query_normalizer import DEFAULT_NORMALIZATION_RULES


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def changed_question_ids(baseline: list[dict[str, Any]], normalized: list[dict[str, Any]]) -> dict[str, list[str]]:
    baseline_by_id = {row["question_id"]: row for row in baseline}
    changes = {"improved": [], "regressed": [], "unchanged": []}
    for row in normalized:
        previous = baseline_by_id[row["question_id"]]
        before = previous.get("first_direct_rank") or 11
        after = row.get("first_direct_rank") or 11
        if after < before:
            changes["improved"].append(f"{row['question_id']} ({before if before <= 10 else '>10'}→{after})")
        elif after > before:
            changes["regressed"].append(f"{row['question_id']} ({before if before <= 10 else '>10'}→{after if after <= 10 else '>10'})")
        else:
            changes["unchanged"].append(row["question_id"])
    return changes


def render_query_normalization_report(
    baseline_summary: dict[str, Any],
    normalized_summary: dict[str, Any],
    baseline_composite: dict[str, Any],
    normalized_composite: dict[str, Any],
    baseline_latency: dict[str, float],
    normalized_latency: dict[str, float],
    baseline_rows: list[dict[str, Any]],
    normalized_rows: list[dict[str, Any]],
) -> str:
    changes = changed_question_ids(baseline_rows, normalized_rows)
    baseline_by_id = {row["question_id"]: row for row in baseline_rows}
    product_rows = [row for row in normalized_rows if row["product_codes"]]
    preserved_product_rows = [
        row
        for row in product_rows
        if row["retrieved_chunk_ids"] == baseline_by_id[row["question_id"]]["retrieved_chunk_ids"]
    ]
    lines = [
        "# BM25-001: 제한적 질의 용어 정규화",
        "",
        "## 가설",
        "",
        "사용자 표현과 연금 문서의 공식 용어 차이가 검색 실패의 주요 원인이다.",
        "",
        "## 범위",
        "",
        "- dev 질문만 사용",
        "- Simple BM25 저장 인덱스 유지",
        "- 질의 토큰만 확장하고 원래 토큰은 삭제하지 않음",
        "- Corpus·문서 토큰·BM25 파라미터·Top-k는 변경하지 않음",
        "",
        "## 정규화 규칙",
        "",
        "| 사용자 표현 | 추가 문서 표현 | 근거 질문 |",
        "|---|---|---|",
    ]
    for phrase, aliases, question_id in DEFAULT_NORMALIZATION_RULES:
        lines.append(f"| {phrase} | {', '.join(aliases)} | {question_id} |")
    lines.extend(
        [
            "",
            "## 결과",
            "",
            "| Variant | R@1 | R@3 | R@5 | R@10 | MRR | p95 ms |",
            "|---|---:|---:|---:|---:|---:|---:|",
            "| Baseline | {} | {} | {} | {} | {:.3f} | {:.2f} |".format(
                percent(baseline_summary["direct_hit_at_1"]),
                percent(baseline_summary["direct_hit_at_3"]),
                percent(baseline_summary["direct_hit_at_5"]),
                percent(baseline_summary["direct_hit_at_10"]),
                baseline_summary["direct_mrr"],
                baseline_latency["p95_ms"],
            ),
            "| Query normalization | {} | {} | {} | {} | {:.3f} | {:.2f} |".format(
                percent(normalized_summary["direct_hit_at_1"]),
                percent(normalized_summary["direct_hit_at_3"]),
                percent(normalized_summary["direct_hit_at_5"]),
                percent(normalized_summary["direct_hit_at_10"]),
                normalized_summary["direct_mrr"],
                normalized_latency["p95_ms"],
            ),
            "",
            "| 복합 근거 (dev) | Baseline All@5 | Baseline All@10 | 정규화 All@5 | 정규화 All@10 |",
            "|---|---:|---:|---:|---:|",
            "| {}개 질문 | {} | {} | {} | {} |".format(
                baseline_composite["question_count"],
                percent(baseline_composite["all_evidence_at_5"]),
                percent(baseline_composite["all_evidence_at_10"]),
                percent(normalized_composite["all_evidence_at_5"]),
                percent(normalized_composite["all_evidence_at_10"]),
            ),
            "",
            "- 상품코드 질의 Top-10 유지: {}/{}개".format(len(preserved_product_rows), len(product_rows)),
            "",
            "## 질문별 변화",
            "",
            "### 개선",
            "",
            "- " + (", ".join(changes["improved"]) or "없음"),
            "",
            "### 회귀",
            "",
            "- " + (", ".join(changes["regressed"]) or "없음"),
            "",
            "### 변화 없음",
            "",
            "- " + ", ".join(changes["unchanged"]),
            "",
        ]
    )
    accepted = (
        normalized_summary["direct_hit_at_5"] >= baseline_summary["direct_hit_at_5"] + 1 / baseline_summary["question_count"]
        and normalized_summary["direct_hit_at_10"] >= baseline_summary["direct_hit_at_10"]
        and not changes["regressed"]
    )
    lines.extend(
        [
            "## 결정",
            "",
            "**{}** — dev Direct R@5 {}. Direct R@10 {}. 회귀 질문: {}개.".format(
                "Accepted" if accepted else "Rejected",
                "개선" if normalized_summary["direct_hit_at_5"] > baseline_summary["direct_hit_at_5"] else "미개선",
                "유지" if normalized_summary["direct_hit_at_10"] >= baseline_summary["direct_hit_at_10"] else "하락",
                len(changes["regressed"]),
            ),
        ]
    )
    return "\n".join(lines) + "\n"
