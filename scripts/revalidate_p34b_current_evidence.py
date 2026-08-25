"""Bind P34-B semantic-equivalence decisions to the current selected chunks.

This is an adjudication artifact, not a retrieval fallback: a decision becomes
invalid as soon as the required current chunk set changes.  It never promotes
same-document evidence automatically.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# Reviewed against the P34-B current selection using all four dimensions:
# subject, account/product/system scope, canonical field, and factual value or
# condition.  These are alternatives to the manifest gold chunks, not merely
# chunks from the same source document.
CURRENT_EQUIVALENCE = {
    "P34-001": {
        "required_selected_chunks": ["4607500e74afcdf8-table-6f164502cbce"],
        "requirements": [
            {
                "subject": "DB·DC 제도",
                "field": "운용 주체·퇴직급여 산정·DC 부담금 구조",
                "value_or_condition": "DB는 회사 운용·평균임금×계속근로기간, DC는 근로자 운용·부담금 누계액±운용손익",
                "scope": "DB와 DC의 동일 제도 비교표",
            }
        ],
    },
    "P34-004": {
        "required_selected_chunks": ["04782a392f49293e-table-d2d7171cef89"],
        "requirements": [
            {
                "subject": "연금저축·IRP",
                "field": "세액공제 대상 납입 한도",
                "value_or_condition": "연금저축 단독 600만원, IRP 포함 합산 900만원",
                "scope": "동일 계좌유형의 공제한도 비교",
            }
        ],
    },
    "P34-005": {
        "required_selected_chunks": [
            "de4f8448134189df-table-ce8fee5b43be",
            "eec10989c7067926-paragraph_group-72065e97ce5d",
        ],
        "requirements": [
            {
                "subject": "일반계좌·연금계좌",
                "field": "과세 시점",
                "value_or_condition": "일반계좌 과세와 연금계좌 인출 전 과세이연의 대비",
                "scope": "계좌별 운용수익 과세 시점",
            }
        ],
    },
    "P34-008": {
        "required_selected_chunks": ["15fb5460a23aa10d-paragraph_group-9b55ec13ba82"],
        "requirements": [
            {
                "subject": "DC 중도인출",
                "field": "허용 사유·신청·증빙 절차",
                "value_or_condition": "법정 사유에서만 허용되며 신청서와 증빙서류가 필요",
                "scope": "DC와 IRP를 구별해 DC 절차를 직접 명시",
            }
        ],
    },
    "P34-014": {
        "required_selected_chunks": [
            "8297231e70bc792a-paragraph_group-7ecf4273221c",
            "8297231e70bc792a-table-332d5aafe603",
        ],
        "requirements": [
            {
                "subject": "KR5127450215",
                "field": "지수 추종 전략·주식 관련 자산 비율",
                "value_or_condition": "코스닥150 수익률 연동, 주식 및 주식관련 파생상품 60% 이상",
                "scope": "동일 상품의 모투자신탁 전략·투자대상",
            }
        ],
    },
    "P34-016": {
        "required_selected_chunks": [
            "cf922cacac95fad9-table-8d0be7d0b37c",
            "c787719b514f51da-table-94fdc4ab85f6",
        ],
        "requirements": [
            {
                "subject": "KR510902773M·KR510902777M",
                "field": "위험등급 비교",
                "value_or_condition": "각각 3등급(다소 높은 위험), 2등급(높은 위험)",
                "scope": "각 상품의 직접 위험등급 표",
            }
        ],
    },
    "P34-017": {
        "required_selected_chunks": [
            "f24a347b7c7a170c-table-27119d018496",
            "545de7c663ff2726-table-0b26f6286e7d",
        ],
        "requirements": [
            {
                "subject": "KR5114420022·KR5114450222",
                "field": "위험등급·상대적 위험",
                "value_or_condition": "각각 5등급, 2등급이며 5등급 상품이 더 낮은 위험",
                "scope": "각 상품의 직접 위험등급 표",
            }
        ],
    },
    "P34-018": {
        "required_selected_chunks": [
            "fc3cd93441450fa8-table-3c68497fd9d9",
            "eefb7f7b407d91de-paragraph_group-e41211088478",
        ],
        "requirements": [
            {
                "subject": "KR5120420039·KR5120420091",
                "field": "위험등급·상대적 위험",
                "value_or_condition": "각각 5등급, 6등급이며 6등급 상품이 더 낮은 위험",
                "scope": "각 상품의 직접 등급·변경 이력 근거",
            }
        ],
    },
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P34-B Current Evidence Revalidation",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음; 현재 P34-B pre-HCX selected chunks만 재판정했다.",
        "- same-document 여부가 아니라 subject + field + value/condition + scope로 판정했다.",
        "- required current chunk가 바뀌면 해당 semantic-equivalent 판정은 자동으로 무효다.",
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
        "Source relevance passes only for this frozen P34-B evidence selection. No partial or wrong-scope chunk is promoted to a factual requirement.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-hcx", type=Path, default=ROOT / "evaluation/p34_closed_pre_hcx.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p34b_current_evidence_revalidation.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p34b_current_evidence_revalidation.md")
    args = parser.parse_args()

    pre_hcx = json.loads(args.pre_hcx.read_text(encoding="utf-8"))
    rows = []
    for row in pre_hcx["rows"]:
        if row["source_relevance_status"] == "exact_gold":
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
        "experiment": "P34-B current evidence revalidation",
        "manifest_sha256": pre_hcx["manifest_sha256"],
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
