"""Attribute the frozen P36 pre-HCX No-Go without changing Agent behaviour.

P36 was a fresh holdout when executed.  This diagnostic consumes only the
frozen manifest and the HCX-free preparation artifact; it neither replays nor
modifies the Agent and never invokes HCX.  P36 is therefore a development /
regression set after this script is run.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash


PRIMARY_OWNERS = (
    "normalization_alias_miss",
    "normalization_semantic_miss",
    "canonical_field_miss",
    "matcher_field_miss",
)


# This table is a human diagnostic annotation of the *frozen* P36 trace.  It
# is intentionally not imported by production code and contains no ID-specific
# routing behaviour.
FAILURE_AUDITS = {
    "P36-002": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["가입자 교육 책임·실시 주체", "최소 연간 주기", "전문기관 위탁 가능 여부"],
        "reason": "‘책임지고 시행’, ‘1년에’, ‘전문기관에 위임’이 participant_education canonical intent와 세 factual slot으로 정규화되지 않아 simple fallback으로 남았다.",
    },
    "P36-003": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["두 배로 움직임 → 레버리지 ETF", "반대로 움직임 → 인버스 ETF"],
        "reason": "DC·IRP ETF 직접매매 entity는 보이지만 배수·반대 추종 표현이 leverage/inverse restriction concept로 정규화되지 않아 restriction plan과 field query가 생성되지 않았다.",
    },
    "P36-004": {
        "primary_owner": "normalization_alias_miss",
        "missing_concepts": ["개인연금 저축계좌 → 연금저축", "개인형퇴직연금 → IRP"],
        "reason": "질문의 두 계좌 표현이 canonical account entity로 결속되지 않아 연금저축 단독과 IRP 포함 한도를 각각 요구하는 tax comparison schema가 발동하지 않았다.",
    },
    "P36-006": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["국내 거래소 상장 해외 ETF", "계좌 밖 → 일반계좌", "일반계좌 대 연금계좌 과세 비교"],
        "reason": "상품 성격과 ‘계좌 밖’의 일반계좌 scope가 foreign ETF account-tax comparison으로 함께 정규화되지 않아 복수 과세 requirement가 생성되지 않았다.",
    },
    "P36-008": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["퇴직 전에 꺼내기 → DC 중도인출", "입증자료 → 신청 절차·증빙"],
        "reason": "중도인출의 간접 표현과 입증자료가 withdrawal condition/procedure concepts로 연결되지 않아 DC 법정 사유와 증빙을 분리한 plan이 만들어지지 않았다.",
    },
    "P36-009": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["ISA가 끝난 뒤 → ISA 만기", "연금계좌로 이전", "이전 후 추가 세액공제 계산"],
        "reason": "‘ISA가 끝난 뒤’가 만기 event로 canonicalize되지 않아 이전 기한과 추가 세액공제라는 두 requirement의 transfer schema가 발동하지 않았다.",
    },
    "P36-010": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["환매하지 않고 사업자 변경 → 실물이전", "DB·DC와 IRP의 신청 경로 비교"],
        "reason": "표면상 사업자 변경이 DB→DC 전환 intent로 먼저 흡수됐다. 환매 없는 이전이라는 operation meaning과 account별 신청 경로가 in-kind transfer schema로 복원되지 않았다.",
    },
    "P36-011": {
        "primary_owner": "normalization_semantic_miss",
        "missing_concepts": ["상승·하락 배수 추종 → 레버리지 ETF", "반대 방향 추종 → 인버스 ETF"],
        "reason": "P36-003과 같은 semantic normalization 공백이다. ETF 직접매매 limitation을 묻지만 배수/반대 추종 표현이 restriction field로 들어가지 않았다.",
    },
    "P36-013": {
        "primary_owner": "canonical_field_miss",
        "missing_concepts": ["투자위험 분류 → risk_grade", "시장 조건·운용 실적에 따른 조정 → risk_grade_changeability"],
        "reason": "product plan은 생성됐지만 위험 분류와 변경 가능성을 generic investment risk/principal loss로 축약했다. 현재 등급과 등급 변경 가능성은 서로 다른 factual fields여야 한다.",
    },
    "P36-014": {
        "primary_owner": "canonical_field_miss",
        "missing_concepts": ["특정 지수 성과 반영 → investment_strategy", "주식 관련 자산 편입 비율 상한 → equity_allocation_limit"],
        "reason": "지수 성과와 편입비율 상한이 product strategy/asset allocation canonical fields로 결속되지 않아 product factual requirement가 생성되지 않았다.",
    },
    "P36-015": {
        "primary_owner": "canonical_field_miss",
        "missing_concepts": ["연간 총보수 비율", "3년 보유 가정 비용 예시", "두 비용 표현의 구분"],
        "reason": "총보수는 인식됐지만 기간 보유 가정 금액이 cost_example field로 분리되지 않았다. 비율과 기간별 금액을 동일 cost field로 취급하면 질문의 field boundary requirement를 놓친다.",
    },
    "P36-017": {
        "primary_owner": "canonical_field_miss",
        "missing_concepts": ["몇 단계 위험 → risk_grade", "보수적으로 분류 → 상대적 낮은 위험 비교"],
        "reason": "두 product subject는 있으나 ‘몇 단계 위험’과 보수적 분류 표현이 risk_grade 및 comparative risk field로 정규화되지 않아 direct field retrieval query가 생성되지 않았다.",
    },
    "P36-018": {
        "primary_owner": "canonical_field_miss",
        "missing_concepts": ["투자위험 분류 → risk_grade", "낮은 위험 단계 → relative risk comparison"],
        "reason": "P36-017과 같은 product field normalization 공백이다. 두 상품의 risk-grade values와 낮은 쪽 비교가 별도 requirement로 만들어지지 않았다.",
    },
    "P36-007": {
        "primary_owner": "matcher_field_miss",
        "missing_concepts": [],
        "reason": "연금저축·IRP 인출 비교 plan과 직접 gold chunks가 candidate에 있었지만, matcher/selection은 ISA 문서의 연금저축 언급과 ISA 이전 문단을 계좌별 인출 범위·IRP 법정 사유 근거로 선택했다. account + field + scope 결속 실패다.",
    },
}


# Non-exact source decisions are tied to the IDs from p36_closed_pre_hcx.json,
# rather than reusing an older holdout's evidence verdict.
SOURCE_AUDITS = {
    "P36-001": {
        "status": "semantic_equivalent",
        "selected_ids": ["4607500e74afcdf8-table-6f164502cbce"],
        "reason": "현재 DB/DC 비교표가 운용 주체, 급여 결정 방식, DC 회사 부담금 구조를 함께 직접 지지한다. gold paragraph와 달라도 subject·field·value·scope가 동일하다.",
    },
    "P36-005": {
        "status": "semantic_equivalent",
        "selected_ids": [
            "de4f8448134189df-table-ce8fee5b43be",
            "eec10989c7067926-paragraph_group-15cf127eb9b9",
        ],
        "reason": "현재 선택 표와 설명 문단이 일반계좌와 연금계좌의 과세 시점 및 과세이연 조건을 직접 비교한다. gold IDs와 달라도 같은 tax timing facts를 지지한다.",
    },
    "P36-007": {
        "status": "wrong_scope",
        "selected_ids": [
            "5a8516a0215f8754-slide-30fa544ed87e",
            "ae22159be59440b6-paragraph_group-8d64cc53348b",
            "e8d7e6a69504e042-paragraph_group-f8ee1dd5d6ec",
        ],
        "reason": "세 번째 문단은 인출 과세 일부를 지지할 수 있지만 앞의 두 selected evidence는 ISA 문서의 연금저축 언급·ISA 이전 문단이다. 연금저축 인출 범위와 IRP 법정 중도인출 사유를 대체할 수 없다.",
    },
    "P36-012": {
        "status": "semantic_equivalent",
        "selected_ids": ["4607500e74afcdf8-table-6f164502cbce"],
        "reason": "현재 DB/DC 비교표가 운용 주체, 급여 결정 방식, DC 부담금 구조를 직접 제시해 db_dc_benefit_calculation schema와 의미적으로 동등하다.",
    },
}


def _source_verdict(row: dict, *, semantic_requirement_coverage: bool) -> tuple[str, str]:
    if not semantic_requirement_coverage:
        return "not_evaluable_due_to_front_end_failure", "semantic requirement plan이 불완전해 source relevance를 factual requirement 단위로 판정할 수 없다."
    audit = SOURCE_AUDITS.get(row["question_id"])
    if audit is not None:
        if audit["selected_ids"] != row["selected_chunk_ids"]:
            raise SystemExit(f"stale source audit: {row['question_id']} selected IDs changed")
        return audit["status"], audit["reason"]
    if row["exact_gold_chunk_ids_selected"]:
        return "exact_gold", "선택 evidence에 frozen manifest gold chunk가 포함되어 있으며 해당 requirement를 직접 지지한다."
    raise SystemExit(f"missing source verdict for fully planned case: {row['question_id']}")


def _case_payload(record: dict, row: dict) -> dict:
    question_id = record["question_id"]
    audit = FAILURE_AUDITS.get(question_id)
    semantic_requirement_coverage = not bool(audit) or question_id == "P36-007"
    status, source_reason = _source_verdict(
        row,
        semantic_requirement_coverage=semantic_requirement_coverage,
    )
    return {
        # Deliberately omit the question text so this diagnostic cannot become a
        # future holdout-builder input by accident.
        "question_id": question_id,
        "category": record["category"],
        "semantic_requirements": record["required_requirements"],
        "actual_requirement_category": row["requirement_category_actual"],
        "actual_slot_keys": row["actual_slot_keys"],
        "semantic_requirement_coverage": semantic_requirement_coverage,
        "evidence_sufficient": row["evidence_sufficient"],
        "selected_chunk_ids": row["selected_chunk_ids"],
        "source_relevance": status,
        "source_relevance_reason": source_reason,
        "primary_owner": audit["primary_owner"] if audit else None,
        "missing_canonical_concepts": audit["missing_concepts"] if audit else [],
        "reason": audit["reason"] if audit else "Semantic requirements and selected source evidence meet the frozen Closed factual contract.",
    }


def _report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# P36-A Closed Pre-HCX Failure Attribution",
        "",
        "## Frozen-run integrity",
        "",
        f"- Manifest SHA-256: `{payload['manifest_sha256']}`",
        "- HCX calls: **0**; this diagnostic only reads the frozen pre-HCX artifact.",
        "- Agent, retriever, matcher, gate, prompt, policy, and evaluator behaviour were **not changed**.",
        "- P36 is now a development/regression set; it must not be reused as generalization evidence after a fix.",
        "",
        "## Result",
        "",
        f"- Semantic requirement coverage: **{summary['semantic_requirement_coverage']}/18**",
        f"- Frozen evidence sufficiency: **{summary['evidence_sufficient']}/18**",
        f"- Original + primary provenance: **{summary['primary_original']}/18**",
        f"- Source relevance among fully planned cases: exact **{summary['source_relevance']['exact_gold']}**, equivalent **{summary['source_relevance']['semantic_equivalent']}**, partial **{summary['source_relevance']['partial']}**, wrong-scope **{summary['source_relevance']['wrong_scope']}**.",
        "",
        "## First-failure owners",
        "",
    ]
    for owner in PRIMARY_OWNERS:
        lines.append(f"- `{owner}`: **{summary['primary_owner_counts'][owner]}**")
    lines.extend((
        "",
        "The 13 semantic requirement failures occur before retrieval ranking: 8 are entity/operation/intent normalization failures and 5 are product field canonicalization failures. P36-007 is the separate matcher/source-scope failure after a correct plan.",
        "",
        "## Source-relevance audit",
        "",
        "Only the five rows with full semantic requirement plans are source-adjudicated. Four pass with exact/equivalent evidence; P36-007 is wrong-scope. Rows whose requirements were not formed are not counted as source-relevance passes merely because they share a document or an exact gold chunk.",
        "",
    ))
    for case in payload["cases"]:
        if case["source_relevance"] in {"semantic_equivalent", "wrong_scope"}:
            lines.append(f"- **{case['question_id']}** — `{case['source_relevance']}`: {case['source_relevance_reason']}")
    lines.extend(("", "## Failed-case attribution", ""))
    for case in payload["cases"]:
        if not case["primary_owner"]:
            continue
        lines.extend((
            f"### {case['question_id']} — `{case['primary_owner']}`",
            "",
            f"- Required facts: {' / '.join(case['semantic_requirements'])}",
            f"- Actual category / slots: `{case['actual_requirement_category']}` / {', '.join(case['actual_slot_keys']) or '없음'}",
            f"- Missing canonical concepts: {' / '.join(case['missing_canonical_concepts']) or '없음'}",
            f"- Evidence sufficient: **{case['evidence_sufficient']}**; source relevance: `{case['source_relevance']}`",
            f"- Attribution: {case['reason']}",
            "",
        ))
    lines.extend((
        "## Gate",
        "",
        "**No-Go.** P36 misses the 18/18 pre-HCX criteria at semantic requirement coverage (5/18), evidence sufficiency (13/18), and source relevance (4/5 fully-planned cases; one wrong-scope). Do not invoke HCX. The next work must be a generalized Closed front-end fix, followed by a new fresh holdout rather than a P36 re-score being treated as generalization evidence.",
        "",
    ))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p36_closed_holdout_manifest.json")
    parser.add_argument("--pre-hcx", type=Path, default=ROOT / "evaluation/p36_closed_pre_hcx.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p36a_failure_attribution.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p36a_failure_attribution.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    frozen = json.loads(args.pre_hcx.read_text(encoding="utf-8"))
    manifest_hash = _manifest_hash(manifest)
    if frozen["manifest_sha256"] != manifest_hash:
        raise SystemExit("P36 pre-HCX artifact belongs to a different frozen manifest")
    if frozen.get("hcx_called") is not False or frozen["summary"].get("hcx_calls") != 0:
        raise SystemExit("P36-A must remain HCX-free")

    frozen_rows = {row["question_id"]: row for row in frozen["rows"]}
    cases = [_case_payload(record, frozen_rows[record["question_id"]]) for record in manifest["questions"]]
    owners = Counter(case["primary_owner"] for case in cases if case["primary_owner"])
    relevance = Counter(case["source_relevance"] for case in cases)
    fully_planned = [case for case in cases if case["semantic_requirement_coverage"]]
    summary = {
        "total": len(cases),
        "semantic_requirement_coverage": sum(case["semantic_requirement_coverage"] for case in cases),
        "evidence_sufficient": frozen["summary"]["evidence_sufficient"],
        "primary_original": frozen["summary"]["primary_original"],
        "primary_owner_counts": {owner: owners[owner] for owner in PRIMARY_OWNERS},
        "source_relevance_population": "fully_planned_semantic_requirements_only",
        "source_relevance": {
            status: relevance[status]
            for status in ("exact_gold", "semantic_equivalent", "partial", "wrong_scope")
        },
        "fully_planned_cases": len(fully_planned),
        "hcx_calls": 0,
    }
    payload = {
        "phase": "P36-A",
        "experiment": "P36 Closed Pre-HCX Failure Attribution",
        "manifest_sha256": manifest_hash,
        "hcx_calls": 0,
        "candidate_code_modified": False,
        "frozen_execution_modified": False,
        "summary": summary,
        "cases": cases,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
