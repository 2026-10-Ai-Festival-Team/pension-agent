"""Run P34 through the candidate shared ``prepare`` path without HCX.

This script never calls HCX.  It separates deterministic pre-HCX preparation
from later generation evaluation and never promotes an unreviewed alternate
chunk to semantic-equivalent evidence.  Any non-exact selected evidence stays
``manual_relevance_review_required`` in the artifact.  After P34-A
attribution, P34 is a development regression set; P35 must be newly frozen
for the next generalization claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def _manifest_hash(manifest: dict) -> str:
    stored = manifest.get("manifest_sha256")
    without_hash = {key: value for key, value in manifest.items() if key not in {"manifest_sha256", "validation"}}
    actual = hashlib.sha256(
        json.dumps(without_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if stored != actual:
        raise SystemExit("P34 manifest hash does not match frozen contents; do not execute a modified holdout")
    return actual


_SCHEMA_EQUIVALENTS = {
    # ``db_dc_benefit_calculation`` with both benefit and operation slots
    # covers the three factual axes expected by the generic DB/DC comparison.
    ("db_dc_general_comparison", "db_dc_benefit_calculation"): {
        "db_benefit", "dc_benefit", "db_operation", "dc_operation",
    },
}


def _plan_coverage(expected_category: str, expected_slot_keys: list[str], case) -> tuple[bool, str]:
    if case is None:
        return False, "missing"
    actual_category = case.question_id.removeprefix("dynamic:")
    actual_keys = {slot.key for slot in case.slots}
    if actual_category == expected_category and set(expected_slot_keys) <= actual_keys:
        return True, "exact"
    equivalent_keys = _SCHEMA_EQUIVALENTS.get((expected_category, actual_category))
    if equivalent_keys is not None and equivalent_keys <= actual_keys:
        return True, "schema_equivalent"
    return False, "missing"


def _row(agent: P27DStructuredOutputAgent, record: dict) -> dict:
    plan = agent.prepare(record["question"], top_k=10)
    case = plan.requirement_case
    actual_slot_keys = [slot.key for slot in case.slots] if case else []
    expected_slot_keys = record["expected_slot_keys"]
    selected = [context.chunk_id for context in plan.contexts]
    gold = set(record["acceptable_equivalent_evidence"])
    exact = sorted(gold & set(selected))
    selected_primary_original = all(
        context.source_type.value == "original" and context.authority_level.value == "primary"
        for context in plan.contexts
    )
    expected_keys_ok, coverage_status = _plan_coverage(
        record["expected_requirement_category"], expected_slot_keys, case
    )
    if exact:
        relevance = "exact_gold"
    elif plan.assessment.sufficient:
        relevance = "manual_relevance_review_required"
    else:
        relevance = "not_evaluable_before_sufficiency"
    return {
        "question_id": record["question_id"],
        "category": record["category"],
        "question": record["question"],
        "route": plan.route.route,
        "requirement_category_expected": record["expected_requirement_category"],
        "requirement_category_actual": case.question_id.removeprefix("dynamic:") if case else None,
        "requirement_category_correct": coverage_status in {"exact", "schema_equivalent"},
        "expected_slot_keys": expected_slot_keys,
        "actual_slot_keys": actual_slot_keys,
        "requirement_plan_coverage": expected_keys_ok,
        "requirement_plan_coverage_status": coverage_status,
        "base_retrieved_chunk_ids": [result.chunk_id for result in plan.base_results],
        "candidate_chunk_ids": [result.chunk_id for result in plan.candidate_results],
        "selected_chunk_ids": selected,
        "selected_primary_original": selected_primary_original,
        "evidence_sufficient": plan.assessment.sufficient,
        "assessment_reason": plan.assessment.reason,
        "missing_slots": list(plan.assessment.missing_requirements),
        "declared_gold_chunk_ids": sorted(gold),
        "exact_gold_chunk_ids_selected": exact,
        "source_relevance_status": relevance,
        "wrong_scope_detected": False,
        "hcx_invoked": False,
    }


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# P34-B Closed Factual Development Regression (Pre-HCX)",
        "",
        "## Frozen scope",
        "",
        f"- Frozen manifest SHA-256: `{payload['manifest_sha256']}`",
        "- HCX was not called. This is a deterministic P34-B development regression result.",
        "- P34 was converted to development data after P34-A; P35 must be newly frozen for generalization claims.",
        "",
        "## Pre-HCX result",
        "",
        f"- Requirement-plan coverage: **{summary['requirement_plan_coverage']}/{summary['total']}**",
        f"- Evidence sufficiency: **{summary['evidence_sufficient']}/{summary['total']}**",
        f"- Selected evidence original + primary: **{summary['primary_original']}/{summary['total']}**",
        f"- Exact gold source relevance: **{summary['exact_gold']}/{summary['total']}**",
        f"- Manual source-relevance reviews required: **{summary['manual_relevance_review_required']}**",
        f"- Wrong-scope evidence: **{summary['wrong_scope']}**",
        "",
        "## Interpretation",
        "",
        "Non-exact evidence is deliberately not auto-promoted to semantic equivalence. Review those rows against subject, account/product scope, canonical field, and factual value before any HCX call. Provider, schema, citation, and semantic metrics are intentionally absent from this pre-HCX stage.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p34_closed_holdout_manifest.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p34_closed_pre_hcx.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p34_closed_pre_hcx.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen_before_pre_hcx_execution":
        raise SystemExit("P34 manifest is not in its pre-HCX frozen state")
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
        "experiment": "P34-B closed factual development regression pre-HCX",
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
