"""Attribute Closed Core preparation failures without calling HCX.

This is intentionally a diagnostic for the development-only benchmark.  It
does not add question-specific behaviour and does not treat the question-bank
``DOC-*`` namespace as retrieval ground truth: that namespace is still
unmapped to corpus source IDs.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _owner(plan) -> tuple[str, str]:
    """Return the first upstream failure owner, without inferring semantics."""
    entities = plan.analysis.extracted_entities
    case = plan.requirement_case

    # A named product with an objective requested field must be resolved before
    # it can safely be labelled a recommendation or searched as generic text.
    if (
        plan.route.route == "unsupported"
        and entities.requested_fields
        and not entities.product_codes
    ):
        return "subject_resolution", "named_product_not_resolved_to_product_code"
    if case is None:
        return "planner_missing", "compound_question_has_no_dynamic_requirement_plan"
    if not plan.candidate_results:
        return "retrieval_missing", "requirement_specific_retrieval_returned_no_candidates"
    if plan.selection is not None and not plan.assessment.sufficient:
        return "matcher_missing", "candidates_exist_but_required_slots_not_satisfied"
    # This deliberately remains diagnostic rather than silently passing rows
    # whose DOC IDs cannot yet be translated to corpus sources.
    return "source_mapping_only", "preparation_incomplete_but_no_lower_layer_owner_is_observable"


def _row(agent: P27DStructuredOutputAgent, record: dict, certification: dict) -> dict | None:
    cert_row = certification[record["id"]]
    if cert_row["evidence_sufficient"]:
        return None
    plan = agent.prepare(record["question"], top_k=10)
    owner, reason = _owner(plan)
    entities = plan.analysis.extracted_entities
    case = plan.requirement_case
    required_doc_ids = sorted(
        item["document_id"]
        for item in record["fixtures"]["retrieval"].get("required_evidence", ())
    )
    return {
        "id": record["id"],
        "question": record["question"],
        "closed_core_group": record["closed_core_group"],
        "primary_owner": owner,
        "owner_reason": reason,
        "route": plan.route.route,
        "route_reasons": list(plan.route.reasons),
        "analysis": {
            "intent": plan.analysis.intent,
            "accounts": list(entities.accounts),
            "product_codes": list(entities.product_codes),
            "requested_fields": list(entities.requested_fields),
            "comparison": entities.comparison,
        },
        "requirement_plan_generated": case is not None,
        "requirement_category": case.question_id.removeprefix("dynamic:") if case else None,
        "required_slot_keys": [slot.key for slot in case.slots] if case else [],
        "candidate_chunk_count": len(plan.candidate_results),
        "selected_chunk_count": len(plan.contexts),
        "assessment_reason": plan.assessment.reason,
        "missing_slots": list(plan.assessment.missing_requirements),
        "required_document_ids": required_doc_ids,
        "document_mapping_status": "unmapped" if required_doc_ids else "not_required",
        "selected_source_paths": cert_row["selected_source_paths"],
    }


def _report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# P33-C2 Closed Core Failure Attribution",
        "",
        "## Scope",
        "",
        "- HCX is not called; this runs the candidate Agent's shared `prepare()` path.",
        "- Closed Core remains a development-only evidence certification benchmark.",
        "- A primary owner is the first observable upstream failure, not a semantic answer label.",
        "",
        "## Result",
        "",
        f"- Preparation-insufficient rows: **{summary['insufficient']}/{summary['total']}**",
    ]
    for owner in ("planner_missing", "subject_resolution", "retrieval_missing", "matcher_missing", "source_mapping_only"):
        lines.append(f"- `{owner}`: **{summary['owner_counts'].get(owner, 0)}**")
    lines.extend((
        f"- DOC-ID provenance still unmapped: **{summary['unmapped_doc_id_rows']}** rows",
        "",
        "## Interpretation",
        "",
        f"The current insufficient set contains **{summary['owner_counts'].get('planner_missing', 0)}** `planner_missing` and **{summary['owner_counts'].get('subject_resolution', 0)}** `subject_resolution` rows. These are upstream of retrieval: the affected rows have candidates, but no requirement plan or product subject identity that can safely bind the evidence.",
        "",
        "The `DOC-*` values are not present in corpus metadata. They are reported as `unmapped`, never converted into a retrieval pass/fail signal. A static provenance bridge must be supplied or verified separately before document-level recall can be certified.",
        "",
    ))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=ROOT / "evaluation/closed_core_benchmark_v1.jsonl")
    parser.add_argument("--certification", type=Path, default=ROOT / "evaluation/closed_core_evidence_certification_v1.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p33c2_closed_core_failure_attribution.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p33c2_closed_core_failure_attribution.md")
    args = parser.parse_args()

    certification_payload = json.loads(args.certification.read_text(encoding="utf-8"))
    certification = {row["id"]: row for row in certification_payload["rows"]}
    agent = P27DStructuredOutputAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    rows = [
        row for record in _jsonl(args.benchmark)
        if (row := _row(agent, record, certification)) is not None
    ]
    owner_counts = Counter(row["primary_owner"] for row in rows)
    payload = {
        "experiment": "P33-C2 Closed Core failure attribution",
        "hcx_called": False,
        "limitations": [
            "Closed Core is a development regression set, not a fresh holdout.",
            "DOC-ID to corpus-source provenance is not available in the current corpus metadata.",
            "This does not adjudicate semantic-equivalent document evidence.",
        ],
        "summary": {
            "total": len(certification_payload["rows"]),
            "insufficient": len(rows),
            "owner_counts": dict(sorted(owner_counts.items())),
            "unmapped_doc_id_rows": sum(bool(row["required_document_ids"]) for row in rows),
        },
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
