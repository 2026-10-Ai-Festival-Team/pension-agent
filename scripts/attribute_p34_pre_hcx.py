"""Freeze manual P34 pre-HCX owner and source-relevance attribution.

P34 is already executed and is now a development regression set.  This script
does not call HCX and does not modify Agent behaviour.  It binds each manual
source-relevance adjudication to the frozen manifest hash *and* to the current
selected evidence IDs, so a later selection change cannot silently reuse the
decision.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PLANNER_ATTRIBUTION = {
    "P34-001": {
        "primary_owner": "planner_intent_miss",
        "reason": "DB/DC 두 entity는 추출됐지만 ‘구별’이 기존 비교 trigger(차이·비교·각각)에 포함되지 않아 requirement plan이 생성되지 않았다.",
        "general_pattern": "비교 의도 동의어(구별·가려내기·대조)를 structural comparison intent로 정규화할 필요",
    },
    "P34-002": {
        "primary_owner": "planner_intent_miss",
        "reason": "가입자 교육의 직접 실시·외부 위임 의미는 있으나 DB/DC scope 또는 ‘위탁’이라는 현재 trigger가 없어 교육 plan이 생성되지 않았다.",
        "general_pattern": "‘외부에 맡기다’ 같은 위탁 동의어와 제도 일반범위 교육 질문의 intent 처리 필요",
    },
    "P34-003": {
        "primary_owner": "planner_intent_miss",
        "reason": "ETF·레버리지·인버스 intent는 명확하지만 ‘퇴직연금 계좌’라는 포괄 scope가 DC/IRP entity predicate를 만족하지 못했다.",
        "general_pattern": "퇴직연금 일반 scope가 DC/IRP 공통 규정에 적용되는 경우의 safe scope expansion 필요",
    },
    "P34-008": {
        "primary_owner": "planner_intent_miss",
        "reason": "‘중간에 꺼내다’와 신청·증빙은 중도인출 절차 intent지만 현재 DC withdrawal rule은 ‘중도인출’과 ‘조건/사유/요건’의 literal trigger를 요구한다.",
        "general_pattern": "중간 인출/돈을 빼다와 사유·절차 결합을 withdrawal procedure intent로 정규화할 필요",
    },
    "P34-012": {
        "primary_owner": "planner_schema_variant",
        "reason": "Agent는 DB/DC 급여산정+운용 plan을 생성했고 evidence gate도 통과했다. P34 manifest가 기대한 general-comparison slot key와 동등 목적의 benefit-calculation slot key가 달라 exact slot-key metric에서만 실패했다.",
        "general_pattern": "향후 plan coverage는 category exact match뿐 아니라 requirement-to-slot semantic coverage를 별도 측정해야 함",
    },
    "P34-014": {
        "primary_owner": "planner_slot_miss",
        "reason": "상품코드 subject는 식별됐지만 ‘지수를 따라가도록 운용’과 ‘비중’이 investment_strategy/investment_target field trigger에 매핑되지 않아 product field plan이 생성되지 않았다.",
        "general_pattern": "지수 추종·편입 비중·자산 비율을 product strategy/target canonical field로 매핑할 필요",
    },
    "P34-018": {
        "primary_owner": "planner_slot_miss",
        "reason": "두 상품코드는 식별됐지만 ‘등급’ 및 ‘더 낮은 위험’이 risk_grade field trigger의 표현 범위 밖이라 two-product slot plan이 생성되지 않았다.",
        "general_pattern": "위험등급·등급 표시·낮은/높은 위험의 안전한 risk_grade synonym boundary 필요",
    },
}


# These decisions are intentionally evidence-level, not question-level.  Each
# required selected ID must still be present; otherwise the record becomes
# stale and must be reviewed again rather than copied forward.
SOURCE_RELEVANCE = {
    "P34-004": {
        "status": "semantic_equivalent",
        "required_selected_ids": ["04782a392f49293e-table-d2d7171cef89"],
        "reason": "현재 표는 연금저축 단독 600만원·IRP 합산 900만원을 직접 제시하며, gold와 다른 문서이지만 동일 scope·field·value를 지지한다.",
    },
    "P34-005": {
        "status": "partial",
        "required_selected_ids": ["eec10989c7067926-paragraph_group-d7d393007f9c"],
        "reason": "세금을 내며 운용/재투자 사례의 도입 문장만 있어 일반계좌 과세 시점과 연금계좌 과세이연 조건·시점을 모두 직접 지지하지 않는다.",
    },
    "P34-008": {
        "status": "wrong_scope",
        "required_selected_ids": ["ef05c9c97fbadd27-paragraph_group-c169d907b699"],
        "reason": "선택 근거는 IRP 중도인출 사유이며 질문의 DC 중도인출 사유·신청·증빙 requirement를 대체할 수 없다.",
    },
    "P34-013": {
        "status": "partial",
        "required_selected_ids": ["cf922cacac95fad9-table-8d0be7d0b37c"],
        "reason": "현재 3등급 값은 직접 지지하지만, 질문의 위험등급 변경 가능성 requirement를 직접 지지하는 문장이 선택 context에 없다.",
    },
    "P34-014": {
        "status": "partial",
        "required_selected_ids": ["8297231e70bc792a-paragraph_group-7ecf4273221c"],
        "reason": "코스닥150 추종 전략은 직접 지지하지만, 질문의 주식 관련 자산 60% 이상 requirement를 selected context가 직접 지지하지 않는다.",
    },
    "P34-016": {
        "status": "semantic_equivalent",
        "required_selected_ids": ["cf922cacac95fad9-table-8d0be7d0b37c", "c787719b514f51da-table-94fdc4ab85f6"],
        "reason": "두 선택 표가 각 product scope에서 각각 3등급·2등급을 직접 지지하므로 gold paragraph와 동등하다.",
    },
    "P34-017": {
        "status": "semantic_equivalent",
        "required_selected_ids": ["f24a347b7c7a170c-table-27119d018496", "545de7c663ff2726-table-0b26f6286e7d"],
        "reason": "각 product의 5등급·2등급을 직접 지지하는 동일 source product 표라 gold paragraph와 동등하다.",
    },
    "P34-018": {
        "status": "semantic_equivalent",
        "required_selected_ids": ["eefb7f7b407d91de-paragraph_group-e41211088478", "fc3cd93441450fa8-table-0f507789a744"],
        "reason": "각 product scope에서 6등급·5등급을 직접 지지해 상대 비교 requirement를 완전히 충족한다.",
    },
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# P34-A Pre-HCX Failure Attribution",
        "",
        "## Scope",
        "",
        f"- Frozen P34 manifest SHA-256: `{payload['manifest_sha256']}`",
        "- HCX 호출 없음. 이 문서는 Agent 수정 전 attribution만 기록한다.",
        "- P34는 이 분석 후 development/regression set이며 generalisation claim에 재사용하지 않는다.",
        "",
        "## Planner / preparation owners",
        "",
    ]
    for owner, count in sorted(summary["planner_owner_counts"].items()):
        lines.append(f"- `{owner}`: **{count}**")
    lines.extend((
        "",
        "## Current source relevance",
        "",
        f"- Exact gold: **{summary['exact_gold']}**",
        f"- Semantic equivalent: **{summary['semantic_equivalent']}**",
        f"- Partial: **{summary['partial']}**",
        f"- Wrong scope: **{summary['wrong_scope']}**",
        f"- Stale adjudications: **{summary['stale_source_reviews']}**",
        "",
        "## Decision",
        "",
        "P34 pre-HCX remains **No-Go**. The primary failure is Planner generalisation; source relevance additionally contains three partial selections and one wrong-scope selection. Do not call HCX. Any later Agent change must be evaluated first on the development regressions, then on a new P35 holdout.",
        "",
    ))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p34_closed_holdout_manifest.json")
    parser.add_argument("--pre-hcx", type=Path, default=ROOT / "evaluation/p34_closed_pre_hcx.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p34a_failure_attribution.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p34a_failure_attribution.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pre_hcx = json.loads(args.pre_hcx.read_text(encoding="utf-8"))
    if pre_hcx["manifest_sha256"] != manifest["manifest_sha256"]:
        raise SystemExit("P34 pre-HCX artifact belongs to a different manifest")
    rows = {row["question_id"]: row for row in pre_hcx["rows"]}
    planner_rows = []
    for question_id, attribution in PLANNER_ATTRIBUTION.items():
        row = rows[question_id]
        if row["requirement_plan_coverage"]:
            raise SystemExit(f"Planner attribution is stale: {question_id} now has full plan coverage")
        planner_rows.append({"question_id": question_id, **attribution})
    source_rows = []
    for question_id, adjudication in SOURCE_RELEVANCE.items():
        row = rows[question_id]
        selected = set(row["selected_chunk_ids"])
        expected = set(adjudication["required_selected_ids"])
        source_rows.append({
            "question_id": question_id,
            **adjudication,
            "adjudication_current": expected <= selected,
        })
    stale = [row["question_id"] for row in source_rows if not row["adjudication_current"]]
    status_counts = Counter(row["status"] for row in source_rows if row["adjudication_current"])
    summary = {
        "total": len(rows),
        "requirement_plan_coverage": sum(row["requirement_plan_coverage"] for row in rows.values()),
        "evidence_sufficient": sum(row["evidence_sufficient"] for row in rows.values()),
        "planner_owner_counts": dict(sorted(Counter(row["primary_owner"] for row in planner_rows).items())),
        "exact_gold": sum(row["source_relevance_status"] == "exact_gold" for row in rows.values()),
        "semantic_equivalent": status_counts["semantic_equivalent"],
        "partial": status_counts["partial"],
        "wrong_scope": status_counts["wrong_scope"],
        "stale_source_reviews": len(stale),
    }
    payload = {
        "experiment": "P34-A pre-HCX failure attribution",
        "hcx_called": False,
        "manifest_sha256": manifest["manifest_sha256"],
        "summary": summary,
        "planner_attribution": planner_rows,
        "source_relevance_attribution": source_rows,
        "stale_source_reviews": stale,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
