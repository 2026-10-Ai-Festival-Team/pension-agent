"""Close the exact Q1A 26-row clarification deficit with frozen F controls."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_f_register_additive as f_builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_bulk_remediation as bulk
from scripts import run_p49_2h_4d_f_register_additive as f_runner

Q1A = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3_q1a_full_allocation_reconstruction_v1.json"
H_RESIDUAL = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_residual_manifest_v1.jsonl"
I_RESIDUAL = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_residual_manifest_v1.jsonl"
POOL_582 = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_cumulative_comparison_pool_v2.jsonl"
MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_live_manifest_v1.jsonl"
PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_live_preflight_v2.json"
TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_live_trace_v1.jsonl"
CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_live_candidates_v1.jsonl"
AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_live_audit_v1.json"
PROMOTION = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_promotion_v1.jsonl"
PROMOTION_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_promotion_audit_v1.json"
POOL_608 = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_cumulative_comparison_pool_v1.jsonl"
I_REPREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_residual_repreflight_v2.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    if path.exists(): raise FileExistsError(f"refusing overwrite: {path}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists(): raise FileExistsError(f"refusing overwrite: {path}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def collisions(dedup: dict[str, Any]) -> int:
    return sum(len(dedup[k]) for k in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))


def plan() -> dict[str, int]:
    rows = bridge.read_jsonl(H_RESIDUAL)
    result = {row["coverage_cell"]: row["deficit"] for row in rows}
    if len(result) != 5 or sum(result.values()) != 26:
        raise ValueError("H authority must retain exact 5-cell / 26 deficit")
    return result


def host_question_checks(row: dict[str, Any], semantic_rows: list[dict[str, Any]], questions: list[str]) -> tuple[dict[str, Any], str, list[str]]:
    adapted, question, host_findings = f_builder.rendered_question(row, semantic_rows)
    caller = bridge.caller_input_for(adapted, questions)
    findings = sorted(set(
        bridge.preservation_findings(row, adapted)
        + bridge.diversity_prompt_findings(row, caller)
        + bridge.field_boundary_prompt_findings(row, adapted, caller)
        + host_findings
    ))
    return adapted, question, findings


def build_rows(source_rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select exact Q1A cells, reusing only F's existing host renderer controls."""
    selected: list[dict[str, Any]] = []
    virtual: list[dict[str, Any]] = []
    used: set[str] = set()
    sequence = 0
    for cell, needed in sorted(plan().items()):
        sources = [row for row in source_rows if row["coverage_cell"] == cell and row["target_outcome"] == "clarification_required"]
        if len(sources) < needed: raise ValueError(f"H source capacity below Q1A deficit for {cell}")
        chosen = 0
        for source in sources:
            if source["remediation_request_id"] in used: continue
            for offset in range(30):
                candidate = f_builder._row_from_source(source, sequence + 1, "clarification_required", "formal", surface_variant_offset=offset)
                candidate.update({
                    "h_source_manifest_request_id": source["remediation_request_id"],
                    "remediation_request_id": f"P49-2H-4D-H-CLAR-{sequence + 1:04d}",
                    "h_clarification_status": "planned_zero_hcx",
                    "q1a_quota_cell": cell,
                })
                try:
                    _, question, findings = host_question_checks(candidate, semantic_rows, [row["question"] for row in [*pool, *virtual]])
                    dedup = bridge.full_set_dedup_audit(pool, [*virtual, {"remediation_request_id": candidate["remediation_request_id"], "validation_status": "pass", "question": question}], bridge.read_jsonl(bridge.FROZEN_SEED))
                except (KeyError, ValueError):
                    continue
                if findings or collisions(dedup): continue
                selected.append(candidate); virtual.append({"remediation_request_id": candidate["remediation_request_id"], "validation_status": "pass", "question": question})
                used.add(source["remediation_request_id"]); sequence += 1; chosen += 1
                break
            if chosen == needed: break
        if chosen != needed: raise ValueError(f"H could not build {needed} clean host-rendered rows for {cell}; found {chosen}")
    if len(selected) != 26 or Counter(row["coverage_cell"] for row in selected) != Counter(plan()):
        raise AssertionError("H manifest escaped Q1A exact allocation")
    return selected


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures, virtual = [], []
    for row in rows:
        try:
            _, question, findings = host_question_checks(row, semantic_rows, [x["question"] for x in [*pool, *virtual]])
            if findings: failures.append({"remediation_request_id": row["remediation_request_id"], "findings": findings})
            virtual.append({"remediation_request_id": row["remediation_request_id"], "validation_status": "pass", "question": question})
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "preflight_error": str(exc)})
    dedup = bridge.full_set_dedup_audit(pool, virtual, bridge.read_jsonl(bridge.FROZEN_SEED))
    return {
        "stage": "P49-2H-4D-H strict clarification preflight",
        "external_hcx_calls": 0, "comparison_pool_pass": len(pool), "requested": len(rows),
        "requested_by_cell": dict(Counter(row["coverage_cell"] for row in rows)),
        "host_question_renderer": "P49-2H-4D-F-host-register-surface-v1",
        "preservation_renderer_semantic_pass": len(rows) - len(failures), "failures": failures,
        "full_set_dedup": dedup, "full_set_dedup_pass": collisions(dedup) == 0,
        "live_execution_allowed": len(rows) == 26 and not failures and collisions(dedup) == 0,
    }


def audit(rows: list[dict[str, Any]], traces: list[dict[str, Any]], candidates: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    findings = Counter(value for trace in traces for value in trace.get("validation_findings", []))
    metrics = f_runner.finding_metrics(traces)
    dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    healthy = len(traces) == len(rows) and all(f_runner.bridge_healthy(trace) for trace in traces)
    passed = [row for row in candidates if row.get("validation_status") == "pass"]
    new = sorted({bulk.failure_class(item) for item in findings} - bulk.KNOWN_FAILURE_CLASSES)
    strict = len(passed) == len(rows) == 26 and healthy and all(value == 0 for value in metrics.values()) and not new and collisions(dedup) == 0 and not any(trace["generation_status"] == "generation_exhausted" for trace in traces)
    return {
        "stage": "P49-2H-4D-H clarification quota closure", "external_hcx_calls": sum(row["attempt_count"] for row in traces),
        "logical_requests": len(rows), "comparison_pool_before": len(pool), "pass": len(passed),
        "generation_exhausted": sum(row["generation_status"] == "generation_exhausted" for row in traces),
        "bridge_healthy": healthy, "strict_findings": {
            "missing_condition_drift": metrics["clarification_missing_condition_drift"], "semantic_drift": metrics["semantic_drift"],
            "evidence_drift": sum("evidence" in item for item in findings), "outcome_drift": sum("outcome" in item for item in findings),
            "subject_provenance_mismatch": sum("subject" in item or "source" in item for item in findings),
            "register_subject_loss": metrics["register_subject_loss"], "register_surface_drift": metrics["register_surface_drift"],
            "near_duplicate": metrics["near_duplicate"], "new_failure_class": len(new),
        }, "validation_findings": dict(findings), "new_failure_classes": new,
        "full_set_dedup": dedup, "full_set_dedup_pass": collisions(dedup) == 0,
        "strict_tranche_quality_go": strict, "promotion_allowed": strict,
        "quota_credit": {"total_before": 526, "clarification_before": 82, "actual_credit": len(passed) if strict else 0, "total_after": 526 + (len(passed) if strict else 0), "clarification_after": 82 + (len(passed) if strict else 0)},
    }


def promote(pool: list[dict[str, Any]], candidates: list[dict[str, Any]], report: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not report["promotion_allowed"] or report["quota_credit"]["actual_credit"] != 26: raise ValueError("H strict gate not closed")
    rows = [deepcopy(row) for row in candidates if row.get("validation_status") == "pass"]
    for row in rows: row.update(quality_pool_promotion_status="promoted_validation_pass", quality_pool_promotion_scope="additive_comparison_pool_only", quality_pool_promotion_is_acceptance=False, h_quota_credit_status="credited_q1a_clarification_deficit")
    combined = [*pool, *rows]; dedup = bridge.full_set_dedup_audit(combined, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    if len(rows) != 26 or collisions(dedup): raise ValueError("H promotion dedup failed")
    return combined, {"stage": "P49-2H-4D-H clarification promotion / 608 pool", "external_hcx_calls": 0, "prior_pool": str(POOL_582), "prior_pool_sha256": hashlib.sha256(POOL_582.read_bytes()).hexdigest(), "prior_pool_count": len(pool), "prior_pool_modified": False, "promoted_count": 26, "new_pool_count": len(combined), "full_608_dedup_pass": True, "quota_credit": report["quota_credit"]}


def re_preflight_i(pool: list[dict[str, Any]]) -> dict[str, Any]:
    rows = bridge.read_jsonl(I_RESIDUAL); total = sum(row["deficit"] for row in rows); dedup = bridge.full_set_dedup_audit(pool, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    return {"stage": "P49-2H-4D-I supported residual re-preflight after H promotion", "external_hcx_calls": 0, "comparison_pool": str(POOL_608), "comparison_pool_sha256": hashlib.sha256(POOL_608.read_bytes()).hexdigest(), "comparison_pool_pass": len(pool), "residual_cells": len(rows), "residual_deficit": total, "q1a_residual_manifest_sha256": hashlib.sha256(I_RESIDUAL.read_bytes()).hexdigest(), "full_set_dedup_pass": collisions(dedup) == 0, "live_execution_allowed": False, "live_execution_block_reason": "I live is explicitly outside the H closure scope"}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--live", action="store_true"); args = parser.parse_args()
    pool = [row for row in bridge.read_jsonl(POOL_582) if row.get("validation_status") == "pass"]
    if len(pool) != 582: parser.error("H requires frozen G3-B 582-PASS pool")
    semantic = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    if not args.live:
        rows = build_rows(bridge.read_jsonl(bridge.REMEDIATION_MANIFEST), semantic, pool); report = preflight(rows, semantic, pool)
        write_jsonl(MANIFEST, rows); write_json(PREFLIGHT, report); print(json.dumps({"external_hcx_calls":0,"requested":len(rows),"preflight_pass":report["live_execution_allowed"]}, ensure_ascii=False)); return
    if not MANIFEST.exists(): parser.error("run H zero-HCX manifest/preflight first")
    rows = bridge.read_jsonl(MANIFEST); report = preflight(rows, semantic, pool)
    if not report["live_execution_allowed"]: parser.error("H strict preflight failed; no HCX call made")
    for path in (TRACE, CANDIDATES, AUDIT, PROMOTION, PROMOTION_AUDIT, POOL_608, I_REPREFLIGHT):
        if path.exists(): parser.error(f"refusing overwrite: {path}")
    generator = bridge.configured_generator(); corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}; seeds = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]; questions = [row["question"] for row in pool]
    traces=[]; candidates=[]
    for row in rows:
        trace, candidate = bridge.execute_adapted_request(row, bridge.adapt_remediation_record(row, semantic), mode="h-clarification-tranche", generator=generator, corpus=corpus, seed_questions=seeds, comparison_questions=questions, max_generation_attempts=1)
        traces.append(trace); bridge.append_jsonl(TRACE,[trace])
        if candidate is not None:
            candidates.append(candidate); bridge.append_jsonl(CANDIDATES,[candidate])
            if candidate.get("validation_status") == "pass": questions.append(candidate["question"])
    result = audit(rows,traces,candidates,pool); write_json(AUDIT,result)
    if result["promotion_allowed"]:
        combined, promotion = promote(pool,candidates,result); write_jsonl(PROMOTION,[row for row in combined if row.get("h_quota_credit_status")]); write_jsonl(POOL_608,combined); write_json(PROMOTION_AUDIT,promotion); write_json(I_REPREFLIGHT,re_preflight_i(combined))
    print(json.dumps({key:result[key] for key in ("external_hcx_calls","logical_requests","pass","generation_exhausted","strict_tranche_quality_go","promotion_allowed")} | {"quota_credit":result["quota_credit"]},ensure_ascii=False))

if __name__ == "__main__": main()
