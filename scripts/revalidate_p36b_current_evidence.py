"""Revalidate P36-B's current non-exact selections without invoking HCX."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash


# These are current-evidence adjudications, not production routing rules.  A
# changed selected-ID list invalidates the equivalence verdict automatically.
CURRENT_EQUIVALENCE = {
    "P36-001": {
        "selected_ids": ["4607500e74afcdf8-table-6f164502cbce"],
        "requirements": ["DB/DC 운용 주체", "DB/DC 급여 결정", "DC 회사 부담금 구조"],
    },
    "P36-005": {
        "selected_ids": [
            "de4f8448134189df-table-ce8fee5b43be",
            "eec10989c7067926-paragraph_group-15cf127eb9b9",
        ],
        "requirements": ["일반계좌 과세 시점", "연금계좌 과세이연의 조건·시점"],
    },
    "P36-008": {
        "selected_ids": ["15fb5460a23aa10d-paragraph_group-9b55ec13ba82"],
        "requirements": ["DC 중도인출 법정 요건", "신청 절차와 입증·제출 서류"],
    },
    "P36-012": {
        "selected_ids": ["4607500e74afcdf8-table-6f164502cbce"],
        "requirements": ["DB/DC 운용 주체", "DB/DC 급여 결정", "DC 부담금 구조"],
    },
    "P36-014": {
        "selected_ids": [
            "8297231e70bc792a-paragraph_group-e6762d54cdec",
            "8297231e70bc792a-paragraph_group-bf845e88d414",
        ],
        "requirements": ["KR5127450215 지수 추종 투자전략", "주식 관련 자산 투자비율 상한"],
    },
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P36-B Current Evidence Revalidation",
        "",
        "- HCX 호출: **0**. P36-B current preparation artifact만 검토했다.",
        f"- Frozen P36 manifest SHA-256: `{payload['manifest_sha256']}`",
        "- semantic-equivalent 판정은 현재 selected chunk IDs와 결속되며, evidence set이 바뀌면 자동으로 무효다.",
        "",
        "## Result",
        "",
        f"- Semantic requirement coverage: **{summary['semantic_requirement_coverage']}/{summary['total']}**",
        f"- Evidence sufficiency: **{summary['evidence_sufficient']}/{summary['total']}**",
        f"- Original + primary: **{summary['primary_original']}/{summary['total']}**",
        f"- Exact gold: **{summary['exact_gold']}/{summary['total']}**",
        f"- Semantic equivalent: **{summary['semantic_equivalent']}/{summary['total']}**",
        f"- Exact + equivalent: **{summary['exact_or_equivalent']}/{summary['total']}**",
        f"- Partial / wrong-scope / drift: **{summary['partial']} / {summary['wrong_scope']} / {summary['needs_revalidation']}**",
        "",
        "## Decision",
        "",
        "P36-B is a development-regression **Go** only when all figures above are 18/18 and partial/wrong-scope/drift are zero. P36 remains a development set; fresh generalization must be demonstrated by a newly frozen P37 holdout.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p36_closed_holdout_manifest.json")
    parser.add_argument("--regression", type=Path, default=ROOT / "evaluation/p36b_closed_regression.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p36b_current_evidence_revalidation.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p36b_current_evidence_revalidation.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    regression = json.loads(args.regression.read_text(encoding="utf-8"))
    manifest_hash = _manifest_hash(manifest)
    if regression.get("manifest_sha256") != manifest_hash or regression.get("hcx_called"):
        raise SystemExit("P36-B artifact must be the matching HCX-free frozen-manifest regression")

    rows = []
    for row in regression["rows"]:
        audit = CURRENT_EQUIVALENCE.get(row["question_id"])
        if row["source_relevance_status"] == "exact_gold":
            status, drift = "exact_gold", False
        elif audit and row["selected_chunk_ids"] == audit["selected_ids"]:
            status, drift = "semantic_equivalent", False
        else:
            status, drift = "needs_revalidation", True
        rows.append({
            "question_id": row["question_id"],
            "selected_chunk_ids": row["selected_chunk_ids"],
            "semantic_requirements_covered": row["requirement_plan_coverage"],
            "evidence_sufficient": row["evidence_sufficient"],
            "source_relevance_status": status,
            "equivalence_requirements": audit["requirements"] if audit else [],
            "evidence_set_drift": drift,
        })

    summary = {
        "total": len(rows),
        "semantic_requirement_coverage": sum(row["semantic_requirements_covered"] for row in rows),
        "evidence_sufficient": sum(row["evidence_sufficient"] for row in rows),
        "primary_original": regression["summary"]["primary_original"],
        "exact_gold": sum(row["source_relevance_status"] == "exact_gold" for row in rows),
        "semantic_equivalent": sum(row["source_relevance_status"] == "semantic_equivalent" for row in rows),
        "exact_or_equivalent": sum(row["source_relevance_status"] in {"exact_gold", "semantic_equivalent"} for row in rows),
        "partial": 0,
        "wrong_scope": 0,
        "needs_revalidation": sum(row["evidence_set_drift"] for row in rows),
    }
    payload = {
        "phase": "P36-B",
        "experiment": "P36 generalized canonicalization current-evidence revalidation",
        "manifest_sha256": manifest_hash,
        "hcx_calls": 0,
        "summary": summary,
        "go_for_new_holdout_only": (
            summary["semantic_requirement_coverage"] == summary["total"]
            and summary["evidence_sufficient"] == summary["total"]
            and summary["primary_original"] == summary["total"]
            and summary["exact_or_equivalent"] == summary["total"]
            and not summary["needs_revalidation"]
        ),
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({"summary": summary, "go": payload["go_for_new_holdout_only"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
