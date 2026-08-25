"""Revalidate P33 semantic equivalents against the *current* selected chunks.

This is an explicit human evidence adjudication record.  An adjudication is
valid only while its required current chunks remain selected; it intentionally
does not follow a question ID across a changed evidence set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# Each entry was rechecked from the current P33-B selected chunk text using
# subject + field + value/condition + account/product/system scope.
CURRENT_EQUIVALENCE = {
    "P33-003": {
        "required_selected_chunks": ["ef05c9c97fbadd27-table-8e56553263f7"],
        "requirements": [{
            "subject": "IRP 설정 대상",
            "field": "단기·단시간 근로자의 설정 가능 여부",
            "value_or_condition": "1년 미만 또는 주 15시간 미만 근로자는 퇴직급여제도 미설정 근로자로서 IRP 설정 대상",
            "scope": "IRP 가입 대상",
        }],
    },
    "P33-012": {
        "required_selected_chunks": [
            "a7eb7560c10ba4f2-paragraph_group-934493173fce",
            "a7eb7560c10ba4f2-paragraph_group-a521f2f07267",
            "a7eb7560c10ba4f2-paragraph_group-c0cbab4ca054",
        ],
        "requirements": [
            {"subject": "KR5174420011", "field": "위험등급", "value_or_condition": "5등급(낮은 위험)", "scope": "동일 상품"},
            {"subject": "KR5174420011", "field": "자산유형·전략", "value_or_condition": "국내 채권 중심 운용", "scope": "동일 상품"},
            {"subject": "KR5174420011", "field": "원금손실 가능성", "value_or_condition": "실적배당·예금자보호 비대상 및 손실 가능", "scope": "동일 상품"},
        ],
    },
    "P33-013": {
        "required_selected_chunks": [
            "ec6207f6286e8df1-table-8819bf6f75c8",
            "ec6207f6286e8df1-paragraph_group-5de913394d3c",
            "745f9a08e811b6b1-table-392c216e0efe",
        ],
        "requirements": [
            {"subject": "KR515302022M", "field": "위험등급·주된 투자대상", "value_or_condition": "2등급 및 국내 주식 60% 이상", "scope": "동일 상품"},
            {"subject": "KR5129420025", "field": "위험등급·주된 투자대상", "value_or_condition": "6등급 및 국내 국공채 중심", "scope": "동일 상품"},
        ],
    },
    "P33-023": {
        "required_selected_chunks": [
            "745f9a08e811b6b1-table-392c216e0efe",
            "745f9a08e811b6b1-paragraph_group-b8cb0320120d",
        ],
        "requirements": [{
            "subject": "6등급 채권형 펀드",
            "field": "예금자보호·원금보장 여부",
            "value_or_condition": "실적배당상품으로 예금자보호 대상이 아니며 원금손실 가능",
            "scope": "동일 채권형 상품",
        }],
    },
    "P33-024": {
        "required_selected_chunks": [
            "d8a6e37c05c58b07-paragraph_group-0f4eb69b3eb4",
            "d8a6e37c05c58b07-paragraph_group-a97233816116",
        ],
        "requirements": [{
            "subject": "KCGI 목표전환형 펀드",
            "field": "전환 후 전략·가격 하락 가능성",
            "value_or_condition": "국내 채권 중심으로 전환해도 전환 과정·원금 손실 가능",
            "scope": "동일 목표전환형 상품",
        }],
    },
    "P33-025": {
        "required_selected_chunks": [
            "71758d888c643ea0-table-660e77513fdd",
            "ac97d050d2b39ec2-table-3c3be297fdb7",
        ],
        "requirements": [{
            "subject": "일반 펀드 투자 판단",
            "field": "과거성과의 장래 보장·적합성 판단",
            "value_or_condition": "과거 실적은 장래 성과를 보장하지 않으며 투자성향 적합성을 확인해야 함",
            "scope": "특정 상품을 지정하지 않은 일반 안전 전제",
        }],
    },
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P33-C4 Current Evidence Revalidation",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음; Agent 및 retrieval logic 변경 없음.",
        "- P33-B의 현재 exact-overlap mismatch 6건만 재판정했다.",
        "- 이전 adjudication을 재사용하지 않고 current selected chunk IDs에 결속했다.",
        "",
        "## Result",
        "",
        f"- Exact gold: **{summary['exact_gold']}/{summary['total']}**",
        f"- Current semantic equivalent: **{summary['semantic_equivalent']}/{summary['total']}**",
        f"- Exact or equivalent: **{summary['exact_or_equivalent']}/{summary['total']}**",
        f"- Partial: **{summary['partial']}**",
        f"- Wrong scope: **{summary['wrong_scope']}**",
        f"- Evidence-set drift requiring revalidation: **{summary['needs_revalidation']}**",
        "",
        "## Decision",
        "",
        "P33 source relevance passes only for this frozen current selection. Any changed required selected chunk invalidates its semantic-equivalent record and requires a new review.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p33-regression", type=Path, default=ROOT / "evaluation/p33b_orchestration_regression.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p33c4_current_evidence_revalidation.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p33c4_current_evidence_revalidation.md")
    args = parser.parse_args()

    regression = json.loads(args.p33_regression.read_text(encoding="utf-8"))
    rows = []
    for row in regression["p33"]["rows"]:
        if not row["declared_acceptable_chunk_ids"]:
            continue
        if row["source_relevance_pass"]:
            rows.append({
                "question_id": row["question_id"],
                "verdict": "exact_gold",
                "selected_chunk_ids": row["selected_chunk_ids"],
                "requirements": [],
            })
            continue
        adjudication = CURRENT_EQUIVALENCE.get(row["question_id"])
        selected = set(row["selected_chunk_ids"])
        if not adjudication or not set(adjudication["required_selected_chunks"]) <= selected:
            rows.append({
                "question_id": row["question_id"],
                "verdict": "needs_revalidation",
                "selected_chunk_ids": row["selected_chunk_ids"],
                "required_selected_chunks": adjudication["required_selected_chunks"] if adjudication else [],
                "requirements": adjudication["requirements"] if adjudication else [],
            })
            continue
        rows.append({
            "question_id": row["question_id"],
            "verdict": "semantic_equivalent",
            "selected_chunk_ids": row["selected_chunk_ids"],
            "required_selected_chunks": adjudication["required_selected_chunks"],
            "requirements": adjudication["requirements"],
        })

    summary = {
        "total": len(rows),
        "exact_gold": sum(row["verdict"] == "exact_gold" for row in rows),
        "semantic_equivalent": sum(row["verdict"] == "semantic_equivalent" for row in rows),
        "partial": sum(row["verdict"] == "partial" for row in rows),
        "wrong_scope": sum(row["verdict"] == "wrong_scope" for row in rows),
        "needs_revalidation": sum(row["verdict"] == "needs_revalidation" for row in rows),
    }
    summary["exact_or_equivalent"] = summary["exact_gold"] + summary["semantic_equivalent"]
    payload = {
        "experiment": "P33-C4 current evidence revalidation",
        "hcx_called": False,
        "adjudication_rule": "subject + field + value/condition + account/product/system scope",
        "summary": summary,
        "source_relevance_gate_pass": (
            summary["exact_or_equivalent"] == summary["total"]
            and summary["partial"] == 0
            and summary["wrong_scope"] == 0
            and summary["needs_revalidation"] == 0
        ),
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({**summary, "source_relevance_gate_pass": payload["source_relevance_gate_pass"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
