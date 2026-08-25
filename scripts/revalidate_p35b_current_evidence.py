"""Certify P35-B's *current* non-exact Closed-Core evidence selections.

P35 is a development regression set after P35-A.  These adjudications are
therefore evaluation metadata, never question-specific Agent behaviour.  Each
semantic-equivalence record is tied to the exact current selected IDs and is
invalid if the selection drifts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash


CURRENT_EQUIVALENCE = {
    "P35-005": {
        "required_selected_chunks": [
            "de4f8448134189df-table-ce8fee5b43be",
            "7878a3be5806fef4-paragraph_group-d24f4b2854ed",
        ],
        "requirements": [
            "일반계좌는 보유기간에 과세되고 연금계좌는 인출 전까지 과세이연",
            "과세이연은 면제가 아니라 인출·연금수령 시점으로 과세가 미뤄지는 구조",
        ],
    },
    "P35-008": {
        "required_selected_chunks": ["15fb5460a23aa10d-paragraph_group-9b55ec13ba82"],
        "requirements": [
            "DC 중도인출은 법정 사유·요건에서만 가능",
            "중도인출신청서와 사유별 증빙서류를 준비해 회사에 제출",
        ],
    },
    "P35-009": {
        "required_selected_chunks": [
            "ae22159be59440b6-table-5897a6d84778",
            "5a8516a0215f8754-slide-bbf8ab17ae0d",
        ],
        "requirements": [
            "ISA 만기자금은 60일 이내 연금계좌로 이전",
            "전환금액의 10%, 최대 300만원을 추가 세액공제 대상으로 계산",
        ],
    },
    "P35-012": {
        "required_selected_chunks": [
            "4607500e74afcdf8-table-6f164502cbce",
            "04782a392f49293e-paragraph_group-5ab22c46ff7c",
        ],
        "requirements": [
            "DB는 회사가 운용하고 평균임금×계속근로기간으로 급여 산정",
            "DC는 근로자가 운용하고 부담금 누계액±운용손익으로 급여 산정",
        ],
    },
}

# ``P35-013`` exposed that slot-key overlap alone could miss the factual
# request about whether a grade can change.  This semantic audit makes that
# requirement explicit without changing the frozen manifest.
ADDITIONAL_SEMANTIC_SLOT_KEYS = {
    "P35-013": {"KR510902773M:risk_grade_changeability"},
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P35-B Current Evidence and Semantic Requirement Revalidation",
        "",
        "## Scope",
        "",
        f"- Frozen P35 manifest SHA-256: `{payload['manifest_sha256']}`",
        "- HCX was not called. This evaluates the current shared preparation result only.",
        "- Semantic equivalents are bound to the selected chunk IDs listed in the artifact; they are not reusable after evidence-set drift.",
        "",
        "## Result",
        "",
        f"- Semantic requirement coverage: **{summary['semantic_requirement_coverage']}/{summary['total']}**",
        f"- Exact gold: **{summary['exact_gold']}/{summary['total']}**",
        f"- Semantic equivalent: **{summary['semantic_equivalent']}/{summary['total']}**",
        f"- Exact or equivalent: **{summary['exact_or_equivalent']}/{summary['total']}**",
        f"- Partial: **{summary['partial']}**",
        f"- Wrong scope: **{summary['wrong_scope']}**",
        f"- Evidence-set drift: **{summary['needs_revalidation']}**",
        "",
        "## Decision",
        "",
        "P35-B is a deterministic development-regression Go when the result is 18/18 with no partial or wrong-scope evidence. It is not fresh-holdout generalization evidence; P36 must remain a separately frozen evaluation.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p35_closed_holdout_manifest.json")
    parser.add_argument("--regression", type=Path, default=ROOT / "evaluation/p35b_closed_regression.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p35b_current_evidence_revalidation.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p35b_current_evidence_revalidation.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest_hash = _manifest_hash(manifest)
    regression = json.loads(args.regression.read_text(encoding="utf-8"))
    if regression.get("manifest_sha256") != manifest_hash:
        raise SystemExit("P35-B regression belongs to a different frozen manifest")
    if regression.get("hcx_called"):
        raise SystemExit("P35-B revalidation requires an HCX-free preparation artifact")

    rows = []
    for row in regression["rows"]:
        question_id = row["question_id"]
        selected = row["selected_chunk_ids"]
        audit = CURRENT_EQUIVALENCE.get(question_id)
        if row["source_relevance_status"] == "exact_gold":
            source_status = "exact_gold"
            drift = False
        elif audit is None:
            source_status = "needs_revalidation"
            drift = True
        elif selected == audit["required_selected_chunks"]:
            source_status = "semantic_equivalent"
            drift = False
        else:
            source_status = "needs_revalidation"
            drift = True
        actual_slots = set(row["actual_slot_keys"])
        additional = ADDITIONAL_SEMANTIC_SLOT_KEYS.get(question_id, set())
        semantic_covered = bool(row["requirement_plan_coverage"]) and additional <= actual_slots
        rows.append({
            "question_id": question_id,
            "selected_chunk_ids": selected,
            "source_relevance_status": source_status,
            "semantic_requirements_covered": semantic_covered,
            "additional_semantic_slot_keys": sorted(additional),
            "equivalence_requirements": audit["requirements"] if audit else [],
            "evidence_set_drift": drift,
        })

    summary = {
        "total": len(rows),
        "semantic_requirement_coverage": sum(row["semantic_requirements_covered"] for row in rows),
        "exact_gold": sum(row["source_relevance_status"] == "exact_gold" for row in rows),
        "semantic_equivalent": sum(row["source_relevance_status"] == "semantic_equivalent" for row in rows),
        "exact_or_equivalent": sum(
            row["source_relevance_status"] in {"exact_gold", "semantic_equivalent"} for row in rows
        ),
        "partial": sum(row["source_relevance_status"] == "partial" for row in rows),
        "wrong_scope": sum(row["source_relevance_status"] == "wrong_scope" for row in rows),
        "needs_revalidation": sum(row["evidence_set_drift"] for row in rows),
    }
    payload = {
        "phase": "P35-B",
        "experiment": "P35 generalized Closed front-end current evidence revalidation",
        "manifest_sha256": manifest_hash,
        "hcx_called": False,
        "summary": summary,
        "go_for_new_holdout_only": (
            summary["semantic_requirement_coverage"] == summary["total"]
            and summary["exact_or_equivalent"] == summary["total"]
            and summary["partial"] == 0
            and summary["wrong_scope"] == 0
            and summary["needs_revalidation"] == 0
        ),
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({"summary": summary, "go": payload["go_for_new_holdout_only"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
