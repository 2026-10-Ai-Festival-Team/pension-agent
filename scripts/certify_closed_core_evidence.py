"""Offline evidence certification for the development-only Closed Core set.

This intentionally stops before HCX.  It measures whether the candidate
preparation path supplies original, primary evidence and whether the available
benchmark provenance can be verified mechanically.  JSON question-bank
``document_id`` values have no corpus-ID mapping, so those rows are reported
as *unmapped*, never silently counted as evidence hits.
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


def _primary_original(context) -> bool:
    return context.source_type.value == "original" and context.authority_level.value == "primary"


def _subject_bound(slot, result) -> bool:
    if not slot.required_subject_terms:
        return True
    searchable = " ".join((result.title or "", result.section or "", result.text, " ".join(result.product_codes))).upper()
    return all(term.upper() in searchable for term in slot.required_subject_terms)


def _row(agent: P27DStructuredOutputAgent, record: dict, bridge: dict[str, dict]) -> dict:
    plan = agent.prepare(record["question"], top_k=10)
    contexts = tuple(plan.contexts)
    case = plan.requirement_case
    expected_paths = set(record["fixtures"]["retrieval"].get("expected_source_paths", ()))
    expected_document_ids = {
        item["document_id"] for item in record["fixtures"]["retrieval"].get("required_evidence", ())
    }
    mapped_documents = [bridge[document_id] for document_id in expected_document_ids if document_id in bridge]
    verified_source_ids = {
        source_id
        for item in mapped_documents
        if item["mapping_status"] == "verified"
        for source_id in item["corpus_source_ids"]
    }
    selected_source_ids = {context.source_id for context in contexts}
    selected_paths = {context.source_path for context in contexts}
    product_matches = [
        match for match in (plan.selection.matches if plan.selection is not None else ())
        if match.slot.required_subject_terms
    ]
    product_binding_ok = all(
        match.covered and _subject_bound(match.slot, match.result) for match in product_matches
    )
    return {
        "id": record["id"],
        "closed_core_group": record["closed_core_group"],
        "question": record["question"],
        "route": plan.route.route,
        "requirement_category": case.question_id.removeprefix("dynamic:") if case else None,
        "evidence_sufficient": plan.assessment.sufficient,
        "assessment_reason": plan.assessment.reason,
        "missing_slots": plan.assessment.missing_requirements,
        "selected_chunk_ids": [context.chunk_id for context in contexts],
        "selected_source_paths": sorted(selected_paths),
        "all_selected_primary_original": all(_primary_original(context) for context in contexts),
        "expected_source_paths": sorted(expected_paths),
        "source_path_recall_status": (
            "not_declared" if not expected_paths else
            "pass" if expected_paths <= selected_paths else "missing_expected_path"
        ),
        "unmapped_required_document_ids": sorted(
            document_id for document_id in expected_document_ids
            if bridge.get(document_id, {}).get("mapping_status") != "verified"
        ),
        "verified_required_document_source_ids": sorted(verified_source_ids),
        "document_source_recall_status": (
            "not_declared" if not expected_document_ids else
            "unmapped" if not verified_source_ids else
            "pass" if verified_source_ids <= selected_source_ids else "missing_expected_source"
        ),
        "product_subject_field_binding": (
            "not_applicable" if not product_matches else
            "pass" if product_binding_ok else "fail"
        ),
        "slot_evidence": [
            {
                "key": match.slot.key,
                "name": match.slot.name,
                "subject_terms": list(match.slot.required_subject_terms),
                "field_terms": list(match.slot.terms),
                "chunk_id": match.result.chunk_id if match.result else None,
                "source_path": match.result.source_path if match.result else None,
            }
            for match in (plan.selection.matches if plan.selection is not None else ())
        ],
    }


def _report(payload: dict) -> str:
    summary = payload["summary"]
    return "\n".join((
        "# Closed Core Evidence Certification v1",
        "",
        "## Scope",
        "",
        "- Development-only 46-question factual benchmark; HCX is not called.",
        "- Uses the same `prepare()` path as the candidate Agent.",
        "- This verifies preparation-time evidence binding, not semantic answer quality.",
        "",
        "## Result",
        "",
        f"- Evidence-sufficient preparation: **{summary['evidence_sufficient']}/{summary['total']}**",
        f"- Selected evidence all original + primary: **{summary['primary_original_pass']}/{summary['total']}**",
        f"- Declared source-path recall: **{summary['source_path_pass']}/{summary['source_path_declared']}**",
        f"- Product subject-field binding (code-bound plans only): **{summary['product_binding_pass']}/{summary['product_binding_checked']}**",
        f"- Verified DOC-ID source recall: **{summary['document_source_recall_pass']}/{summary['document_source_recall_checked']}**",
        f"- Rows with unresolved DOC-ID provenance: **{summary['unmapped_document_id_rows']}**",
        "",
        "## Interpretation",
        "",
        "Only `verified` records in the separate DOC-ID bridge can contribute to automatic document-source recall. Unresolved IDs are neither source-recall passes nor retrieval failures. Product binding is measured only when the requirement plan is code-bound; `0/0` would mean an observability gap rather than a 0% score.",
        "",
        "A source-path failure, incomplete gate, or subject-field binding failure is retained in the JSON artifact for diagnosis; this report does not relabel it as semantic equivalence automatically.",
        "",
    ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=ROOT / "evaluation/closed_core_benchmark_v1.jsonl")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/closed_core_evidence_certification_v1.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/closed_core_evidence_certification_v1.md")
    parser.add_argument("--document-bridge", type=Path, default=ROOT / "data/provenance/document_id_bridge_v1.json")
    args = parser.parse_args()

    bridge = {
        item["document_id"]: item
        for item in json.loads(args.document_bridge.read_text(encoding="utf-8"))["records"]
    }
    agent = P27DStructuredOutputAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    rows = [_row(agent, record, bridge) for record in _jsonl(args.benchmark)]
    source_declared = [row for row in rows if row["expected_source_paths"]]
    binding_checked = [row for row in rows if row["product_subject_field_binding"] != "not_applicable"]
    document_checked = [row for row in rows if row["document_source_recall_status"] in {"pass", "missing_expected_source"}]
    summary = {
        "total": len(rows),
        "group_counts": dict(sorted(Counter(row["closed_core_group"] for row in rows).items())),
        "evidence_sufficient": sum(row["evidence_sufficient"] for row in rows),
        "primary_original_pass": sum(row["all_selected_primary_original"] for row in rows),
        "source_path_declared": len(source_declared),
        "source_path_pass": sum(row["source_path_recall_status"] == "pass" for row in source_declared),
        "product_binding_checked": len(binding_checked),
        "product_binding_pass": sum(row["product_subject_field_binding"] == "pass" for row in binding_checked),
        "document_source_recall_checked": len(document_checked),
        "document_source_recall_pass": sum(row["document_source_recall_status"] == "pass" for row in document_checked),
        "unmapped_document_id_rows": sum(bool(row["unmapped_required_document_ids"]) for row in rows),
    }
    payload = {
        "experiment": "Closed Core evidence certification v1",
        "hcx_called": False,
        "limitations": [
            "Unresolved DOC-ID records cannot contribute to automatic document-source recall.",
            "This is a preparation/evidence certification, not semantic answer scoring.",
            "Closed Core is a development regression set, not a fresh holdout.",
        ],
        "summary": summary,
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
