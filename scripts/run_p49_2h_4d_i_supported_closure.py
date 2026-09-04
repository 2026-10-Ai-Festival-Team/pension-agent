"""Execute the frozen I1A 48-record supported closure and assemble Final Acceptance 600."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_p49_2h_4d_i1_supported_preflight as i_preflight
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts import run_p49_2h_4d_f_register_additive as f_runner

Q1A = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3_q1a_full_allocation_reconstruction_v1.json"
POOL_608 = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_cumulative_comparison_pool_v1.jsonl"
MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_manifest_v4_i1a.jsonl"
PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_preflight_v6_i1a_surface_repair.json"
I_RESIDUAL = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_residual_manifest_v1.jsonl"
TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_live_trace_v1.jsonl"
CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_live_candidates_v1.jsonl"
AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_live_audit_v1.json"
PROMOTION = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_promotion_v1.jsonl"
PROMOTION_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_promotion_audit_v1.json"
POOL_656 = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_cumulative_comparison_pool_v1.jsonl"
ACCEPTANCE = ROOT / "evaluation/fine_tuning/p49_2h_final_acceptance_600_manifest_v1.jsonl"
ACCEPTANCE_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_final_acceptance_600_audit_v1.json"

SUPPORTED_BEFORE, TOTAL_BEFORE = 342, 552
SUPPORTED_TARGET, TOTAL_TARGET = 390, 600
DEDUP_KEYS = ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing overwrite: {path}")
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing overwrite: {path}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def collisions(dedup: dict[str, Any]) -> int:
    return sum(len(dedup[key]) for key in DEDUP_KEYS)


def residual_plan() -> dict[str, int]:
    rows = bridge.read_jsonl(I_RESIDUAL)
    plan = {row["coverage_cell"]: row["deficit"] for row in rows}
    if len(plan) != 41 or sum(plan.values()) != 48:
        raise ValueError("I authority must retain the exact 41-cell / 48 deficit")
    return plan


def validate_authority(rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> None:
    report = read_json(PREFLIGHT)
    required = {
        "requested": 48, "comparison_pool_pass": 608, "external_hcx_calls": 0,
        "field_scope_drift": 0, "semantic_drift": 0, "subject_preservation": 48,
        "canonical_requirement_preservation": 48, "full_set_dedup_pass": True,
        "live_execution_allowed": True,
    }
    if any(report.get(key) != value for key, value in required.items()):
        raise ValueError("I1A human-approved preflight authority is not frozen GO")
    if len(pool) != 608 or len(rows) != 48 or Counter(row["coverage_cell"] for row in rows) != Counter({
        cell: count for cell, count in residual_plan().items()
    }):
        raise ValueError("I manifest/pool escaped the approved 48 logical-request allocation")
    current = i_preflight.preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    if not current["live_execution_allowed"] or current["full_set_dedup_pass"] is not True:
        raise ValueError("I final host-question strict preflight no longer passes; no HCX call made")


def quota_credit(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], strict_go: bool) -> dict[str, Any]:
    plan = residual_plan()
    candidate_by_id = {candidate.get("remediation_request_id"): candidate for candidate in candidates if candidate.get("validation_status") == "pass"}
    if len(candidate_by_id) != sum(candidate.get("validation_status") == "pass" for candidate in candidates):
        raise ValueError("double credit candidate identity detected")
    credited_by_cell: dict[str, int] = {}
    surplus_by_cell: dict[str, int] = {}
    for cell, limit in plan.items():
        matching = [row for row in rows if row["coverage_cell"] == cell and row["remediation_request_id"] in candidate_by_id]
        if len(matching) > limit:
            raise ValueError(f"I candidate exceeds Q1A deficit for {cell}")
        credited_by_cell[cell] = len(matching)
        surplus_by_cell[cell] = 0
    actual = sum(credited_by_cell.values()) if strict_go else 0
    return {
        "supported_before": SUPPORTED_BEFORE, "total_before": TOTAL_BEFORE,
        "q1a_supported_deficit": sum(plan.values()), "credited_by_cell": credited_by_cell,
        "surplus_by_cell": surplus_by_cell, "double_credit": False,
        "actual_supported_credit": actual,
        "supported_after": SUPPORTED_BEFORE + actual,
        "total_after": TOTAL_BEFORE + actual,
    }


def audit(rows: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    metrics = f_runner.finding_metrics(traces)
    dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    passed = [candidate for candidate in candidates if candidate.get("validation_status") == "pass"]
    healthy = len(traces) == len(rows) and all(f_runner.bridge_healthy(trace) for trace in traces)
    new_classes = sorted({bulk.failure_class(finding) for finding in findings} - bulk.KNOWN_FAILURE_CLASSES)
    strict_findings = {
        "supported_required_fact_omission": findings["supported_required_fact_omission"],
        "adjacent_field_expansion": sum("adjacent" in finding for finding in findings),
        "unsupported_fact_expansion": sum("unsupported" in finding or "caveat" in finding for finding in findings),
        "semantic_drift": metrics["semantic_drift"],
        "evidence_drift": sum("evidence" in finding for finding in findings),
        "outcome_drift": sum("outcome" in finding for finding in findings),
        "subject_provenance_mismatch": sum("subject" in finding or "provenance" in finding or "source" in finding for finding in findings),
        "forbidden_field_expansion": findings["semantic_forbidden_field_expansion"],
        "near_duplicate_candidate": metrics["near_duplicate"],
        "generation_exhausted": sum(trace.get("generation_status") == "generation_exhausted" for trace in traces),
        "new_failure_class": len(new_classes),
    }
    strict_go = len(passed) == len(rows) == 48 and healthy and not findings and not new_classes and collisions(dedup) == 0
    credit = quota_credit(rows, candidates, strict_go)
    return {
        "stage": "P49-2H-4D-I supported quota closure",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "logical_requests": len(rows), "comparison_pool_before": len(pool), "pass": len(passed),
        "bridge_healthy": healthy, "validation_findings": dict(findings),
        "strict_findings": strict_findings, "new_failure_classes": new_classes,
        "full_set_dedup": dedup, "full_set_dedup_pass": collisions(dedup) == 0,
        "strict_tranche_quality_go": strict_go, "promotion_allowed": strict_go and credit["actual_supported_credit"] == 48,
        "quota_credit": credit,
        "augmentation_generation_status": "closed" if credit["total_after"] == TOTAL_TARGET else "not_closed",
    }


def promote(pool: list[dict[str, Any]], candidates: list[dict[str, Any]], report: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not report["promotion_allowed"]:
        raise ValueError("I promotion requires the strict 48/48 tranche gate")
    promoted = [deepcopy(row) for row in candidates if row.get("validation_status") == "pass"]
    for row in promoted:
        row.update(
            quality_pool_promotion_status="promoted_validation_pass",
            quality_pool_promotion_scope="additive_comparison_pool_only",
            quality_pool_promotion_is_acceptance=False,
            i_quota_credit_status="credited_q1a_supported_deficit",
        )
    combined = [*pool, *promoted]
    dedup = bridge.full_set_dedup_audit(combined, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    if len(combined) != 656 or len(promoted) != 48 or collisions(dedup):
        raise ValueError("I promotion pool freeze failed")
    return combined, {
        "stage": "P49-2H-4D-I promotion / final 656 quality pool freeze",
        "external_hcx_calls": 0, "prior_pool": str(POOL_608),
        "prior_pool_sha256": hashlib.sha256(POOL_608.read_bytes()).hexdigest(),
        "prior_pool_count": len(pool), "prior_pool_modified": False,
        "promoted_count": len(promoted), "new_pool_count": len(combined),
        "full_set_dedup_pass": True, "quota_credit": report["quota_credit"],
    }


def candidate_id(row: dict[str, Any]) -> str:
    return str(row.get("remediation_request_id") or row.get("full_request_id") or "")


def final_acceptance(pool: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    q1a = read_json(Q1A)
    targets = {row["coverage_cell"]: row["allocation_target"] for row in q1a["rows"]}
    lanes = {row["coverage_cell"]: row["lane"] for row in q1a["rows"]}
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        if row.get("validation_status") == "pass":
            by_cell[row.get("coverage_cell")].append(row)
    selected: list[dict[str, Any]] = []
    for cell, target in targets.items():
        options = by_cell[cell]
        if len(options) < target:
            raise ValueError(f"Final Acceptance cannot satisfy Q1A cell {cell}: {len(options)}/{target}")
        selected.extend(options[:target])
    ids = [candidate_id(row) for row in selected]
    lane_counts = Counter(row.get("target_outcome") or row.get("outcome") for row in selected)
    integrity = {
        "accepted_candidate_id_unique": len(ids) == len(selected) == len(set(ids)) and all(ids),
        "lineage_integrity": all(row.get("coverage_cell") in targets and (row.get("target_outcome") or row.get("outcome")) == lanes[row["coverage_cell"]] for row in selected),
        "double_credit": False,
        "provenance_integrity": all(bool(row.get("host_question_contract")) and bool(row.get("question")) for row in selected),
        "evidence_outcome_integrity": all(row.get("validation_status") == "pass" and row.get("outcome") == row.get("target_outcome") for row in selected),
    }
    dedup = bridge.full_set_dedup_audit([], selected, bridge.read_jsonl(bridge.FROZEN_SEED))
    quotas = {"supported_answer": 390, "clarification_required": 108, "bounded_answer": 102}
    cell_counts = Counter(row["coverage_cell"] for row in selected)
    integrity_ok = all(value for key, value in integrity.items() if key != "double_credit") and not integrity["double_credit"]
    accepted = len(selected) == TOTAL_TARGET and dict(lane_counts) == quotas and cell_counts == Counter(targets) and integrity_ok and collisions(dedup) == 0
    manifest_id = "P49-2H-Final-Acceptance-600-v1"
    frozen = []
    for row in selected:
        item = deepcopy(row)
        item.update(final_acceptance_manifest_id=manifest_id, acceptance_status="accepted_final_600", quality_pool_promotion_is_acceptance=True)
        frozen.append(item)
    audit = {
        "stage": "P49-2H Final Acceptance 600 Assembly preflight",
        "external_hcx_calls": 0, "quality_pool_count": len(pool), "quality_pool_surplus": len(pool) - TOTAL_TARGET,
        "accepted_count": len(frozen), "lane_counts": dict(lane_counts),
        "q1a_cell_targets": targets, "q1a_cell_selected": dict(cell_counts),
        "integrity": integrity, "full_set_dedup": dedup, "full_set_dedup_pass": collisions(dedup) == 0,
        "accepted_candidate_ids_sha256": hashlib.sha256("\n".join(ids).encode("utf-8")).hexdigest(),
        "acceptance_manifest_sha256": hashlib.sha256("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in frozen).encode("utf-8")).hexdigest(),
        "final_acceptance_go": accepted, "training_export_allowed": False, "tuning_allowed": False,
    }
    return frozen, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Execute exactly the frozen I 48 logical requests.")
    parser.add_argument("--assemble-only", action="store_true", help="Write Final Acceptance 600 from an already frozen 656-pool; HCX calls remain zero.")
    args = parser.parse_args()
    if args.live == args.assemble_only:
        parser.error("choose exactly one of --live or --assemble-only")
    if args.assemble_only:
        if ACCEPTANCE.exists() or ACCEPTANCE_AUDIT.exists():
            parser.error("Final Acceptance artifact already exists; refusing overwrite")
        report = read_json(AUDIT)
        if not report.get("promotion_allowed") or report.get("quota_credit", {}).get("total_after") != TOTAL_TARGET:
            parser.error("Final Acceptance requires the completed I 48/48 strict GO and 600/600 reconciliation")
        pool = [row for row in bridge.read_jsonl(POOL_656) if row.get("validation_status") == "pass"]
        if len(pool) != 656:
            parser.error("Final Acceptance requires the frozen 656-PASS quality pool")
        accepted, acceptance_audit = final_acceptance(pool)
        if not acceptance_audit["final_acceptance_go"]:
            raise RuntimeError("Final Acceptance 600 audit did not pass")
        write_jsonl(ACCEPTANCE, accepted)
        write_json(ACCEPTANCE_AUDIT, acceptance_audit)
        print(json.dumps({"external_hcx_calls": 0, "accepted_count": len(accepted), "final_acceptance_go": True}, ensure_ascii=False))
        return
    rows = bridge.read_jsonl(MANIFEST)
    pool = [row for row in bridge.read_jsonl(POOL_608) if row.get("validation_status") == "pass"]
    validate_authority(rows, pool)
    for path in (TRACE, CANDIDATES, AUDIT, PROMOTION, PROMOTION_AUDIT, POOL_656, ACCEPTANCE, ACCEPTANCE_AUDIT):
        if path.exists():
            parser.error(f"refusing overwrite: {path}")
    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seeds = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    semantic = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    questions = [row["question"] for row in pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        trace, candidate = bridge.execute_adapted_request(
            row, bridge.adapt_remediation_record(row, semantic), mode="i-supported-tranche",
            generator=generator, corpus=corpus, seed_questions=seeds, comparison_questions=questions,
            max_generation_attempts=3,
        )
        traces.append(trace)
        bridge.append_jsonl(TRACE, [trace])
        if candidate is not None:
            candidates.append(candidate)
            bridge.append_jsonl(CANDIDATES, [candidate])
            if candidate.get("validation_status") == "pass":
                questions.append(candidate["question"])
    report = audit(rows, traces, candidates, pool)
    write_json(AUDIT, report)
    if report["promotion_allowed"]:
        combined, promotion = promote(pool, candidates, report)
        write_jsonl(PROMOTION, [row for row in combined if row.get("i_quota_credit_status")])
        write_jsonl(POOL_656, combined)
        write_json(PROMOTION_AUDIT, promotion)
        accepted, acceptance_audit = final_acceptance(combined)
        if not acceptance_audit["final_acceptance_go"]:
            raise RuntimeError("600 quota closed but Final Acceptance 600 audit did not pass")
        write_jsonl(ACCEPTANCE, accepted)
        write_json(ACCEPTANCE_AUDIT, acceptance_audit)
    print(json.dumps({
        "logical_requests": report["logical_requests"], "external_hcx_calls": report["external_hcx_calls"],
        "pass": report["pass"], "strict_go": report["strict_tranche_quality_go"],
        "quota_credit": report["quota_credit"], "promotion_allowed": report["promotion_allowed"],
        "final_acceptance_created": ACCEPTANCE.exists(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
