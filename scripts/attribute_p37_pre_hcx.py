"""Read-only attribution for the frozen P37 pre-HCX failure trace.

The script consumes P37 artifacts only.  It does not import or replay the
candidate Agent and never invokes HCX, so candidate-code freeze is preserved.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash


AUDITS = {
    "P37-002": ("normalization_semantic_miss", "교육 시행 책임·최소 주기·전문기관 대행이 participant_education으로 구조화되지 않았다."),
    "P37-003": ("normalization_semantic_miss", "‘두 배로 키움’과 ‘역방향으로 따름’이 leverage/inverse restriction concepts로 정규화되지 않았다."),
    "P37-004": ("normalization_alias_miss", "‘개인용 연금 저축 계좌’가 연금저축 subject alias로 결속되지 않았다."),
    "P37-005": ("normalization_semantic_miss", "‘일반 투자계좌’와 운용이익 과세 시점이 일반계좌 대 연금계좌 tax timing comparison으로 결속되지 않았다."),
    "P37-007": ("planner_multi_requirement_miss", "계좌별 인출 범위·IRP 법정사유는 계획됐지만 ‘인출 세율’이 tax-treatment slot을 추가하는 semantic modifier로 인식되지 않았다."),
    "P37-008": ("normalization_semantic_miss", "‘근무 중 사용’과 ‘확인 문서’가 DC withdrawal condition/procedure concepts로 정규화되지 않았다."),
    "P37-009": ("normalization_semantic_miss", "ISA ‘종료’ event가 maturity transfer event로 canonicalize되지 않았다."),
    "P37-010": ("normalization_semantic_miss", "매각 없는 운영 금융기관 변경이 in-kind transfer action으로 복원되지 않고 ‘운영’에 의해 DB/DC operation plan으로 흡수됐다."),
    "P37-011": ("normalization_semantic_miss", "‘가격 움직임을 배가’와 ‘반대로 추적’이 ETF leverage/inverse restriction fields로 연결되지 않았다."),
    "P37-013": ("canonical_field_miss", "위험 분류 단계와 시장·운용 결과에 따른 분류 변동 여지가 risk_grade + risk_grade_changeability로 분리되지 않았다."),
    "P37-014": ("canonical_field_miss", "성과 기준 지수와 주식성 자산 최대 편입률이 investment_strategy + investment_target fields로 결속되지 않았다."),
    "P37-015": ("canonical_field_miss", "연 단위 보수 비율과 기간 투자 금액이 total_fee + cost_example field boundary로 분해되지 않았다."),
    "P37-018": ("canonical_field_miss", "리스크 분류 단계와 낮은 위험 수준 비교가 product risk-grade values 및 comparison requirement로 구조화되지 않았다."),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p37_closed_holdout_manifest.json")
    parser.add_argument("--pre-hcx", type=Path, default=ROOT / "evaluation/p37_closed_pre_hcx.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p37a_failure_attribution.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p37a_failure_attribution.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pre_hcx = json.loads(args.pre_hcx.read_text(encoding="utf-8"))
    manifest_hash = _manifest_hash(manifest)
    if pre_hcx.get("manifest_sha256") != manifest_hash or pre_hcx.get("hcx_called") is not False:
        raise SystemExit("P37-A requires the matching HCX-free frozen run")

    rows = []
    for row in pre_hcx["rows"]:
        audit = AUDITS.get(row["question_id"])
        rows.append({
            "question_id": row["question_id"],
            "semantic_requirement_coverage": row["requirement_plan_coverage"],
            "evidence_sufficient": row["evidence_sufficient"],
            "actual_requirement_category": row["requirement_category_actual"],
            "actual_slot_keys": row["actual_slot_keys"],
            "primary_owner": audit[0] if audit else None,
            "reason": audit[1] if audit else "P37 pre-HCX requirement plan passed; source relevance is deferred until every plan is complete.",
        })
    owners = Counter(row["primary_owner"] for row in rows if row["primary_owner"])
    summary = {
        "total": len(rows),
        "semantic_requirement_coverage": sum(row["semantic_requirement_coverage"] for row in rows),
        "evidence_sufficient": sum(row["evidence_sufficient"] for row in rows),
        "primary_original": pre_hcx["summary"]["primary_original"],
        "primary_owner_counts": dict(sorted(owners.items())),
        "hcx_calls": 0,
    }
    payload = {
        "phase": "P37-A",
        "manifest_sha256": manifest_hash,
        "hcx_calls": 0,
        "candidate_code_modified": False,
        "summary": summary,
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P37-A Closed Pre-HCX Failure Attribution", "",
        f"- Manifest SHA-256: `{manifest_hash}`", "- HCX calls: **0**; candidate code was not modified.",
        "- P37 is now a development/regression set.", "",
        "## Result", "",
        f"- Semantic requirement coverage: **{summary['semantic_requirement_coverage']}/18**",
        f"- Evidence sufficiency: **{summary['evidence_sufficient']}/18**",
        f"- Original + primary: **{summary['primary_original']}/18**", "",
        "## First-failure owners", "",
    ]
    lines.extend(f"- `{owner}`: **{count}**" for owner, count in summary["primary_owner_counts"].items())
    lines.extend(("", "## Interpretation", "",
        "P37 repeats the same broad weakness after P34--P36: 9 indirect action/intent phrasings and 4 product-field phrasings fail before retrieval. This is not a retrieval or HCX-generation result. Do not call HCX.",
        "", "## Decision", "",
        "**No-Go.** A further alias list would likely create another phrase-specific regression cycle. The next design step should reconsider the canonicalizer as a compositional subject/action/field/modifier parser before creating a new fresh holdout.", "",
    ))
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
