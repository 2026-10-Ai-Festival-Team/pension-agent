"""Run exactly the approved eight-record P49-2H-4D-G2 bounded anchor smoke.

G2 is intentionally isolated from register taxonomy and Batch-08.  It uses
the existing guarded 4C bridge, canonical v4 candidate construction,
hydration, and validator.  The full 529-PASS comparison pool is always used
for caller retry context and aggregate dedup.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_g1_bounded_anchor_inventory as g1
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.run_p49_2h_full_adapter import semantic_question_findings


APPROVED_ANCHORS = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_human_approved_v1.jsonl"
COMPARISON_POOL = g1.COMPARISON_POOL
DEFAULT_TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_trace_v1.jsonl"
DEFAULT_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_candidates_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_audit_v1.json"
DEFAULT_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g2_bounded_anchor_smoke_preflight_v1.json"
CELL_PLAN = {
    "D12-Q12-bounded_answer": 1,
    "D17-Q17-bounded_answer": 1,
    "D18-Q18-bounded_answer": 1,
    "D20-Q12-bounded_answer": 1,
    "D30-Q17-bounded_answer": 4,
}
LEGACY_REGISTERS = frozenset({"general", "conversational", "beginner"})


def select_g2_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("coverage_cell") in CELL_PLAN]
    counts = Counter(row["coverage_cell"] for row in selected)
    if dict(counts) != CELL_PLAN or len(selected) != 8:
        raise ValueError(f"G2 must contain exact cell plan {CELL_PLAN}; found {dict(counts)}")
    ids = [row.get("remediation_request_id") for row in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("G2 contains duplicate remediation request IDs")
    return sorted(selected, key=lambda row: row["remediation_request_id"])


def preflight(selected: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    """Fail closed before HCX on review, contract, and entire-pool dedup."""
    failures: list[dict[str, Any]] = []
    questions = [row["question"] for row in pool]
    for row in selected:
        request_id = row["remediation_request_id"]
        anchor = row.get("bounded_linguistic_anchor", {})
        if anchor.get("authoring_status") != "human_written" or anchor.get("human_review_status") != "human_approved":
            failures.append({"remediation_request_id": request_id, "anchor_review": "not_human_written_and_approved"})
            continue
        if row.get("register") not in LEGACY_REGISTERS:
            failures.append({"remediation_request_id": request_id, "unexpected_register_taxonomy": row.get("register")})
            continue
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller = bridge.caller_input_for(adapted, questions)
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller)
            semantic = semantic_question_findings(anchor["anchor_question"], adapted["semantic_request"])
            if preservation or diversity or boundary or semantic:
                failures.append({
                    "remediation_request_id": request_id,
                    "preservation_findings": preservation,
                    "diversity_prompt_findings": diversity,
                    "field_boundary_prompt_findings": boundary,
                    "anchor_semantic_findings": semantic,
                })
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": request_id, "adapter_error": str(exc)})
    provisional = [{
        "remediation_request_id": row["remediation_request_id"],
        "validation_status": "pass",
        "generation_status": "not_generated_g2_preflight",
        "question": row["bounded_linguistic_anchor"]["anchor_question"],
    } for row in selected]
    dedup = bridge.full_set_dedup_audit(pool, provisional, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    return {
        "stage": "P49-2H-4D-G2 bounded anchor smoke preflight",
        "external_hcx_calls": 0,
        "requested": len(selected),
        "requested_by_cell": dict(Counter(row["coverage_cell"] for row in selected)),
        "register_taxonomy_experiment_applied": False,
        "human_written_human_approved": len(selected) - sum("anchor_review" in item for item in failures),
        "preservation_prompt_and_semantic_pass": len(selected) - len(failures),
        "failures": failures,
        "full_529_pool_dedup": dedup,
        "full_529_pool_dedup_pass": collisions == 0,
        "live_execution_allowed": not failures and collisions == 0,
    }


def audit(selected: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in candidates if row.get("validation_status") == "pass"]
    pass_by_cell = Counter(row.get("coverage_cell") for row in passed)
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    full_dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(full_dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    bridge_healthy = len(traces) == len(selected) and all(
        trace["caller_input_preservation_pass"]
        and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"]
        and trace["external_call_success"]
        and trace["response_schema_valid"]
        and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success"
        and trace["validator_executed"]
        for trace in traces
    )
    d30_unique_pass = pass_by_cell[g1.D30_CELL]
    requested = len(selected)
    strict_quality = (
        len(passed) == requested
        and not findings
        and collisions == 0
        and bridge_healthy
    )
    return {
        "stage": "P49-2H-4D-G2 bounded anchor smoke",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "requested": requested,
        "requested_by_cell": dict(Counter(row["coverage_cell"] for row in selected)),
        "register_taxonomy_experiment_applied": False,
        "candidate_question_authority": "host_owned_human_approved_anchor",
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "semantic_evidence_outcome_pass": len(passed),
        "pass_by_cell": dict(pass_by_cell),
        "d30_unique_pass": d30_unique_pass,
        "anchor_space_validation_go": d30_unique_pass >= 3 and not findings and collisions == 0,
        "strict_tranche_quality_go": strict_quality,
        "bridge_healthy": bridge_healthy,
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": [],
        "cumulative_full_set_dedup": full_dedup,
        "cumulative_full_set_dedup_pass": collisions == 0,
        "cumulative_quality_pool_before": len(pool),
        "promotion_eligible_pass_count": len(passed),
        "cumulative_quality_pool_if_promoted": len(pool) + len(passed),
        "promotion_allowed": strict_quality and d30_unique_pass >= 3,
        "batch_08_original_manifest_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite G2 artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow only this approved eight-record HCX smoke.")
    parser.add_argument("--input", type=Path, default=APPROVED_ANCHORS)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--trace-output", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")
    selected = select_g2_rows(bridge.read_jsonl(args.input))
    pool = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(pool) != 529:
        parser.error(f"expected frozen 529-PASS comparison pool; found {len(pool)}")
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    report = preflight(selected, semantic_rows, pool)
    if not args.live:
        write_new_json(args.preflight_output, report)
        print(json.dumps({"external_hcx_calls": 0, "requested": len(selected), "preflight_pass": report["preservation_prompt_and_semantic_pass"], "dedup_pass": report["full_529_pool_dedup_pass"], "live_execution_allowed": report["live_execution_allowed"]}, ensure_ascii=False))
        return
    if not report["live_execution_allowed"]:
        parser.error("G2 preflight failed; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"G2 live artifact already exists; choose new path: {path}")
    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    comparison_questions = [row["question"] for row in pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in selected:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row, adapted, mode="anchor-smoke", generator=generator, corpus=corpus,
            seed_questions=seed_questions, comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["register_taxonomy_experiment_applied"] = False
        trace["g2_anchor_smoke_cell"] = row["coverage_cell"]
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])
    result = audit(selected, traces, candidates, pool)
    write_new_json(args.audit_output, result)
    print(json.dumps({key: result[key] for key in (
        "external_hcx_calls", "requested", "semantic_evidence_outcome_pass", "d30_unique_pass",
        "anchor_space_validation_go", "strict_tranche_quality_go", "bridge_healthy", "promotion_allowed",
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
