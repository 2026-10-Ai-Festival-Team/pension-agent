"""Build the zero-HCX, one-record P49-2H-4D-E2A answer omission retest."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_e_register_tranche as register_builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_4d_e2_host_renderer import render_host_question
from scripts.run_p49_2h_full_adapter import semantic_question_findings


SOURCE_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_manifest_v3.jsonl"
TARGET_SOURCE_ID = "P49-2H-4D-E2-HOST-0007"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_repair_preflight_v1.json"
TARGET_REQUIREMENT = "retirement_pension.ETF.direct_trade_scope"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2A answer-repair artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_row(source_rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]]) -> dict[str, Any]:
    source = next((row for row in source_rows if row["remediation_request_id"] == TARGET_SOURCE_ID), None)
    if source is None:
        raise ValueError("E2A target source is missing from E2 manifest")
    row = dict(source)
    if row["target_outcome"] != "supported_answer" or row["canonical_requirement"] != TARGET_REQUIREMENT:
        raise ValueError("E2A target source is not the approved IRP ETF supported requirement")
    adapted = bridge.adapt_remediation_record(row, semantic_rows)
    binding = {
        "canonical_requirement": TARGET_REQUIREMENT,
        "required_answer_terms": list(adapted["answer_contract"]["required_terms"]),
        "required_literal_quotes": list(adapted["literal_evidence_quotes"]),
    }
    row["e2a_source_request_id"] = TARGET_SOURCE_ID
    row["remediation_request_id"] = "P49-2H-4D-E2A-ETF-0001"
    row["supported_answer_completeness"] = binding
    row["e2a_status"] = "planned_zero_hcx"
    return row


def preflight(row: dict[str, Any], semantic_rows: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    try:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
        preservation = bridge.preservation_findings(row, adapted)
        diversity = bridge.diversity_prompt_findings(row, caller_input)
        boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
        question = render_host_question(adapted["semantic_request"], adapted["remediation_control"])
        semantic = semantic_question_findings(question, adapted["semantic_request"])
        register = bridge.register_surface_and_subject_findings(row, adapted, question)
        if preservation or diversity or boundary or semantic or register:
            failures.append({
                "remediation_request_id": row["remediation_request_id"],
                "preservation_findings": preservation,
                "diversity_prompt_findings": diversity,
                "field_boundary_prompt_findings": boundary,
                "host_question_semantic_findings": semantic,
                "register_findings": register,
            })
    except (KeyError, ValueError) as exc:
        failures.append({"remediation_request_id": row["remediation_request_id"], "preflight_error": str(exc)})
        question = ""
    synthetic = [{
        "remediation_request_id": row["remediation_request_id"],
        "validation_status": "pass",
        "generation_status": "not_generated_e2a_preflight",
        "question": question,
    }]
    dedup = bridge.full_set_dedup_audit(current_pool, synthetic, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    return {
        "stage": "P49-2H-4D-E2A Supported Answer Omission Repair Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(current_pool),
        "target_requirement": TARGET_REQUIREMENT,
        "host_question": question,
        "supported_answer_completeness": row["supported_answer_completeness"],
        "preservation_prompt_renderer_semantic_pass": not failures,
        "failures": failures,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "live_execution_allowed": not failures and collisions == 0 and len(current_pool) == 435,
        "initial_e_candidate_promotion_held": True,
        "e1_candidate_promotion_held": True,
        "e2_candidate_promotion_held": True,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    row = build_row(read_jsonl(args.source_manifest), semantic_rows)
    current_pool, _ = register_builder.current_quality_pool()
    report = preflight(row, semantic_rows, current_pool)
    report.update({
        "source_manifest": str(args.source_manifest),
        "source_manifest_sha256": hashlib.sha256(args.source_manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
    })
    write_new(args.output, json.dumps(row, ensure_ascii=False) + "\n")
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": report["comparison_pool_pass"],
        "target_requirement": report["target_requirement"],
        "preflight_pass": report["preservation_prompt_renderer_semantic_pass"],
        "dedup_pass": report["full_set_dedup_pass"],
        "live_execution_allowed": report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
