"""Execute the frozen P37 shared preparation path only; never call HCX."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash, _row
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p37_closed_holdout_manifest.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p37_closed_pre_hcx.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p37_closed_pre_hcx.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen_before_pre_hcx_execution":
        raise SystemExit("P37 manifest is not in its frozen pre-HCX state")
    manifest_hash = _manifest_hash(manifest)
    agent = P27DStructuredOutputAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    rows = [_row(agent, record) for record in manifest["questions"]]
    summary = {
        "total": len(rows),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "requirement_plan_coverage": sum(row["requirement_plan_coverage"] for row in rows),
        "evidence_sufficient": sum(row["evidence_sufficient"] for row in rows),
        "primary_original": sum(row["selected_primary_original"] for row in rows),
        "exact_gold": sum(row["source_relevance_status"] == "exact_gold" for row in rows),
        "manual_relevance_review_required": sum(row["source_relevance_status"] == "manual_relevance_review_required" for row in rows),
        "wrong_scope": sum(row["wrong_scope_detected"] for row in rows),
        "hcx_calls": 0,
    }
    payload = {
        "experiment": "P37 fresh Closed factual pre-HCX holdout",
        "manifest_sha256": manifest_hash,
        "hcx_called": False,
        "criteria": manifest["pre_hcx_go_criteria"],
        "summary": summary,
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text("\n".join((
        "# P37 Fresh Closed Factual Holdout — Pre-HCX",
        "",
        f"- Manifest SHA-256: `{manifest_hash}`",
        "- Shared preparation only; HCX calls: **0**.",
        f"- Requirement-plan coverage: **{summary['requirement_plan_coverage']}/{summary['total']}**",
        f"- Evidence sufficiency: **{summary['evidence_sufficient']}/{summary['total']}**",
        f"- Original + primary: **{summary['primary_original']}/{summary['total']}**",
        f"- Exact gold: **{summary['exact_gold']}/{summary['total']}**; manual current source reviews: **{summary['manual_relevance_review_required']}**.",
        "",
        "Do not invoke HCX unless semantic requirements, evidence sufficiency, provenance, and current exact-or-equivalent source relevance are all 18/18 with no partial or wrong-scope evidence.",
        "",
    )), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
