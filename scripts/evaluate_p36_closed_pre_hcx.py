"""Run frozen P36 through shared preparation only; HCX is unavailable."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluate_p34_closed_pre_hcx import ROOT, _manifest_hash, _row
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P36 Fresh Closed Factual Holdout — Pre-HCX",
        "",
        "## Frozen execution",
        "",
        f"- Manifest SHA-256: `{payload['manifest_sha256']}`",
        "- Shared preparation path only; HCX calls: **0**.",
        "- Non-exact selected chunks are not auto-promoted. They require a current evidence adjudication on subject, field, value/condition, and scope.",
        "",
        "## Raw pre-HCX result",
        "",
        f"- Requirement-plan coverage: **{summary['requirement_plan_coverage']}/{summary['total']}**",
        f"- Evidence sufficiency: **{summary['evidence_sufficient']}/{summary['total']}**",
        f"- Original + primary evidence: **{summary['primary_original']}/{summary['total']}**",
        f"- Exact gold: **{summary['exact_gold']}/{summary['total']}**",
        f"- Current source reviews required: **{summary['manual_relevance_review_required']}**",
        f"- Wrong scope (automatic): **{summary['wrong_scope']}**",
        "",
        "## Gate",
        "",
        "Do not invoke HCX unless semantic requirement coverage, evidence sufficiency, provenance, and current exact-or-equivalent source relevance are all 18/18 with no partial or wrong-scope evidence.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p36_closed_holdout_manifest.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p36_closed_pre_hcx.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p36_closed_pre_hcx.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen_before_pre_hcx_execution":
        raise SystemExit("P36 manifest is not in its frozen pre-HCX state")
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
        "manual_relevance_review_required": sum(
            row["source_relevance_status"] == "manual_relevance_review_required" for row in rows
        ),
        "wrong_scope": sum(row["wrong_scope_detected"] for row in rows),
        "hcx_calls": 0,
    }
    payload = {
        "experiment": "P36 fresh Closed factual pre-HCX holdout",
        "manifest_sha256": manifest_hash,
        "hcx_called": False,
        "criteria": manifest["pre_hcx_go_criteria"],
        "summary": summary,
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
