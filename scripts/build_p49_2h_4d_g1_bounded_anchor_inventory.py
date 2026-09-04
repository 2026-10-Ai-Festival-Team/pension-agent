"""Prepare P49-2H-4D-G1 bounded-anchor inventory with zero HCX calls.

This is deliberately an additive planning/review artifact.  It freezes the
bounded coverage shortfall against the reconciled 529-PASS comparison pool,
reuses only *unused* human-approved anchors from the successful D pilot, and
creates four D30-Q17 review drafts.  A D30 draft is never represented as a
human-written anchor, so the existing execution bridge will refuse a live HCX
call until a person has actually rewritten and approved it.
"""
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

from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.run_p49_2h_full_adapter import semantic_question_findings


MANIFEST = bridge.REMEDIATION_MANIFEST
COMPARISON_POOL = ROOT / "evaluation/fine_tuning/p49_2h_4d_g_cumulative_comparison_pool_v1.jsonl"
APPROVED_D_ANCHORS = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_linguistic_anchor_human_approved_v1.jsonl"
FROZEN_SEED = bridge.FROZEN_SEED
DEFAULT_INVENTORY = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_inventory_v1.json"
DEFAULT_SMOKE_DRAFTS = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_smoke_drafts_v1.jsonl"
DEFAULT_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g1_bounded_anchor_preflight_v1.json"

G2_EXISTING_CELLS = (
    "D12-Q12-bounded_answer",
    "D17-Q17-bounded_answer",
    "D18-Q18-bounded_answer",
    "D20-Q12-bounded_answer",
)
D30_CELL = "D30-Q17-bounded_answer"
G2_CELLS = (*G2_EXISTING_CELLS, D30_CELL)
UNUSED_APPROVED_D_ANCHOR_IDS = {
    "D12-Q12-bounded_answer": "P49-2H-4D-D-ANCHOR-0003",
    "D17-Q17-bounded_answer": "P49-2H-4D-D-ANCHOR-0006",
    "D18-Q18-bounded_answer": "P49-2H-4D-D-ANCHOR-0009",
    "D20-Q12-bounded_answer": "P49-2H-4D-D-ANCHOR-0012",
}

# These are review drafts, not human-written anchors.  They intentionally use
# distinct speech acts so a reviewer can replace them with genuinely authored
# wording rather than merely approve a cluster of paraphrases.
D30_DRAFT_SPECS: tuple[dict[str, str], ...] = (
    {
        "anchor_question": "이 상품을 장기 보유하려는데, 앞으로 수익률이나 위험등급이 구체적으로 어떻게 될지는 지금 자료에서 알 수 없는 건가요?",
        "linguistic_archetype": "장기 보유 계획에서 미래 값의 자료 범위를 확인하는 질문",
        "context_frame": "장기 보유 계획 중",
        "query_form": "evidence_limit",
        "length_band": "medium",
        "speech_act": "자료 범위 확인",
        "information_gap_mode": "근거 범위 점검",
        "temporal_expression": "앞으로",
        "misconception_type": "향후 시점에도 같은 값이라는 전제",
        "sentence_shape": "계획절+정보공백 확인",
    },
    {
        "anchor_question": "현재 안내에는 이 상품의 미래 수익률이나 위험등급 수치가 안 보이는데, 다음 시점의 값까지 이미 정해져 있나요?",
        "linguistic_archetype": "안내문 확인 중 미래 수치의 확정 여부를 묻는 질문",
        "context_frame": "공시자료 검토 중",
        "query_form": "assumption_check",
        "length_band": "medium",
        "speech_act": "확정 여부 확인",
        "information_gap_mode": "현재 정보와 미래 확정값 구분",
        "temporal_expression": "다음",
        "misconception_type": "현재 정보가 미래 값을 보장한다는 전제",
        "sentence_shape": "상황절+확정전제 확인",
    },
    {
        "anchor_question": "이 상품에 투자할 계획인데, 내년에 적용될 위험등급이나 예상 수익률을 지금 기준으로 정해진 값처럼 봐도 되나요?",
        "linguistic_archetype": "투자 계획에서 미래 값 확정이라는 오해를 점검하는 질문",
        "context_frame": "계약 체결 직전",
        "query_form": "misconception",
        "length_band": "medium",
        "speech_act": "오해 전제 확인",
        "information_gap_mode": "미래 수치 미확정 점검",
        "temporal_expression": "미래",
        "misconception_type": "미래 값이 이미 확정됐다는 전제",
        "sentence_shape": "상황절+확정전제 확인",
    },
    {
        "anchor_question": "이 상품의 향후 수익률과 위험등급이 언제·어느 정도가 될지까지 제공 자료로 확인할 수 있나요?",
        "linguistic_archetype": "직접적으로 미래 값과 시점의 확인 가능성을 묻는 질문",
        "context_frame": "공시자료 검토 중",
        "query_form": "direct",
        "length_band": "short",
        "speech_act": "자료 범위 확인",
        "information_gap_mode": "근거 범위 점검",
        "temporal_expression": "향후",
        "misconception_type": "미래 값이 이미 확정됐다는 전제",
        "sentence_shape": "상황절+근거범위 확인",
    },
)


def bounded_inventory(manifest_rows: list[dict[str, Any]], pool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute every bounded cell quota from immutable source + frozen pool."""
    bounded_sources = [row for row in manifest_rows if row.get("target_outcome") == "bounded_answer"]
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in bounded_sources:
        by_cell[row["coverage_cell"]].append(row)
    current = Counter(
        row.get("coverage_cell") for row in pool_rows
        if row.get("validation_status") == "pass" and row.get("outcome", row.get("target_outcome")) == "bounded_answer"
    )
    cells: list[dict[str, Any]] = []
    for cell in sorted(by_cell):
        source_rows = by_cell[cell]
        targets = {int(row["target_count"]) for row in source_rows}
        if len(targets) != 1:
            raise ValueError(f"inconsistent bounded target count in {cell}")
        target = targets.pop()
        cells.append({
            "coverage_cell": cell,
            "target_count": target,
            "current_unique_pass": current[cell],
            "deficit": max(0, target - current[cell]),
            "manifest_request_count": len(source_rows),
        })
    target_total = sum(item["target_count"] for item in cells)
    current_total = sum(item["current_unique_pass"] for item in cells)
    return {
        "bounded_target": target_total,
        "bounded_current_unique_pass": current_total,
        "bounded_deficit": target_total - current_total,
        "cells": cells,
    }


def _fresh_reused_anchor(row: dict[str, Any], sequence: int) -> dict[str, Any]:
    result = deepcopy(row)
    original_request_id = result["remediation_request_id"]
    original_anchor_id = result["bounded_linguistic_anchor"]["anchor_id"]
    result["anchor_source_manifest_request_id"] = result["anchor_source_manifest_request_id"]
    result["reused_human_approved_anchor_request_id"] = original_request_id
    result["remediation_request_id"] = f"P49-2H-4D-G1-ANCHOR-{sequence:04d}"
    result["bounded_linguistic_anchor"] = {
        **result["bounded_linguistic_anchor"],
        "anchor_id": f"P49-2H-4D-G1-ANCHOR-TEXT-{sequence:04d}",
        "reused_from_anchor_id": original_anchor_id,
    }
    result["g1_anchor_kind"] = "reused_human_approved_unused_anchor"
    result["g1_smoke_status"] = "ready_for_hcx_after_whole_tranche_review_gate"
    return result


def _d30_draft_row(source: dict[str, Any], spec: dict[str, str], sequence: int) -> dict[str, Any]:
    result = deepcopy(source)
    result["anchor_source_manifest_request_id"] = result["remediation_request_id"]
    result["remediation_request_id"] = f"P49-2H-4D-G1-D30-DRAFT-{sequence:04d}"
    result["context_frame"] = spec["context_frame"]
    result["query_form"] = spec["query_form"]
    result["register"] = "general"  # no register-taxonomy experiment in G1
    result["length_band"] = spec["length_band"]
    result["bounded_diversity_profile"] = {
        "profile_id": f"D30-Q17-bounded_answer-g1-draft-{sequence:02d}",
        "user_situation_frame": spec["context_frame"],
        "speech_act": spec["speech_act"],
        "information_gap_mode": spec["information_gap_mode"],
        "temporal_expression": spec["temporal_expression"],
        "misconception_type": spec["misconception_type"],
        "sentence_shape": spec["sentence_shape"],
    }
    result["bounded_linguistic_anchor"] = {
        "anchor_id": f"P49-2H-4D-G1-D30-DRAFT-TEXT-{sequence:04d}",
        "anchor_question": spec["anchor_question"],
        "linguistic_archetype": spec["linguistic_archetype"],
        "authoring_status": "drafted_by_codex",
        "human_review_status": "human_review_required",
    }
    result["g1_anchor_kind"] = "d30_codex_draft_pending_actual_human_rewrite"
    result["g1_smoke_status"] = "blocked_human_rewrite_and_approval_required"
    return result


def build_g2_draft_rows(manifest_rows: list[dict[str, Any]], approved_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build four ready reused anchors plus four explicitly blocked D30 drafts."""
    approved_by_id = {row["remediation_request_id"]: row for row in approved_rows}
    rows: list[dict[str, Any]] = []
    for index, cell in enumerate(G2_EXISTING_CELLS, start=1):
        anchor_id = UNUSED_APPROVED_D_ANCHOR_IDS[cell]
        anchor = approved_by_id.get(anchor_id)
        if anchor is None or anchor.get("coverage_cell") != cell:
            raise ValueError(f"missing unused approved D anchor for {cell}: {anchor_id}")
        embedded = anchor.get("bounded_linguistic_anchor", {})
        if embedded.get("authoring_status") != "human_written" or embedded.get("human_review_status") != "human_approved":
            raise ValueError(f"approved D anchor is not human approved: {anchor_id}")
        rows.append(_fresh_reused_anchor(anchor, index))
    d30_sources = [row for row in manifest_rows if row.get("coverage_cell") == D30_CELL]
    if len(d30_sources) < len(D30_DRAFT_SPECS):
        raise ValueError("immutable manifest lacks enough D30-Q17 sources")
    for index, spec in enumerate(D30_DRAFT_SPECS, start=1):
        rows.append(_d30_draft_row(d30_sources[index - 1], spec, index))
    return rows


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], comparison_pool: list[dict[str, Any]]) -> dict[str, Any]:
    """Check adapter/prompt/question semantics and full 529-pool dedup, no HCX."""
    failures: list[dict[str, Any]] = []
    questions = [row["question"] for row in comparison_pool]
    for row in rows:
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, questions)
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            semantic = semantic_question_findings(row["bounded_linguistic_anchor"]["anchor_question"], adapted["semantic_request"])
            if preservation or diversity or boundary or semantic:
                failures.append({
                    "remediation_request_id": row["remediation_request_id"],
                    "preservation_findings": preservation,
                    "diversity_prompt_findings": diversity,
                    "field_boundary_prompt_findings": boundary,
                    "anchor_semantic_findings": semantic,
                })
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    draft_candidates = [{
        "remediation_request_id": row["remediation_request_id"],
        "validation_status": "pass",
        "generation_status": "not_generated_g1_anchor_preflight",
        "question": row["bounded_linguistic_anchor"]["anchor_question"],
    } for row in rows]
    dedup = bridge.full_set_dedup_audit(comparison_pool, draft_candidates, bridge.read_jsonl(FROZEN_SEED))
    collision_count = sum(len(dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    ready = sum(
        row["bounded_linguistic_anchor"]["authoring_status"] == "human_written"
        and row["bounded_linguistic_anchor"]["human_review_status"] == "human_approved"
        for row in rows
    )
    return {
        "external_hcx_calls": 0,
        "requested": len(rows),
        "requested_by_cell": {cell: sum(row["coverage_cell"] == cell for row in rows) for cell in G2_CELLS},
        "preservation_prompt_and_semantic_pass": len(rows) - len(failures),
        "failures": failures,
        "human_written_human_approved": ready,
        "drafted_by_codex_human_review_required": len(rows) - ready,
        "full_529_pool_dedup": dedup,
        "full_529_pool_dedup_pass": collision_count == 0,
        "register_taxonomy_experiment_applied": False,
        "g2_hcx_execution_allowed": False,
        "g2_hcx_block_reason": "D30 draft anchors require actual human rewrite and human approval",
    }


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite immutable G1 artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--comparison-pool", type=Path, default=COMPARISON_POOL)
    parser.add_argument("--approved-d-anchors", type=Path, default=APPROVED_D_ANCHORS)
    parser.add_argument("--inventory-output", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--smoke-drafts-output", type=Path, default=DEFAULT_SMOKE_DRAFTS)
    parser.add_argument("--preflight-output", type=Path, default=DEFAULT_PREFLIGHT)
    args = parser.parse_args()

    manifest_rows = bridge.read_jsonl(args.manifest)
    pool = [row for row in bridge.read_jsonl(args.comparison_pool) if row.get("validation_status") == "pass"]
    if len(pool) != 529:
        parser.error(f"expected frozen 529-PASS comparison pool; found {len(pool)}")
    inventory = bounded_inventory(manifest_rows, pool)
    if (inventory["bounded_current_unique_pass"], inventory["bounded_target"], inventory["bounded_deficit"]) != (59, 102, 43):
        parser.error("bounded inventory does not match frozen 59/102/43 baseline")
    rows = build_g2_draft_rows(manifest_rows, bridge.read_jsonl(args.approved_d_anchors))
    report = preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    inventory.update({
        "stage": "P49-2H-4D-G1 Bounded Anchor Inventory / Human Authoring",
        "external_hcx_calls": 0,
        "comparison_pool_count": len(pool),
        "comparison_pool_sha256": hashlib.sha256(args.comparison_pool.read_bytes()).hexdigest(),
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
        "priority_zero_yield_cells": list(G2_CELLS),
        "d30_priority_deficit": 16,
        "g2_small_smoke_plan": {**{cell: 1 for cell in G2_EXISTING_CELLS}, D30_CELL: 4},
        "g2_hcx_execution_allowed": False,
        "g2_hcx_block_reason": "D30 has four Codex drafts awaiting actual human rewrite and approval",
        "batch_08_original_manifest_allowed": False,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    })
    write_new(args.inventory_output, json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")
    write_new(args.smoke_drafts_output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.preflight_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool": len(pool),
        "bounded_current_unique_pass": inventory["bounded_current_unique_pass"],
        "bounded_target": inventory["bounded_target"],
        "bounded_deficit": inventory["bounded_deficit"],
        "g2_records": len(rows),
        "ready_human_approved": report["human_written_human_approved"],
        "blocked_drafts": report["drafted_by_codex_human_review_required"],
        "preflight_pass": report["preservation_prompt_and_semantic_pass"],
        "dedup_pass": report["full_529_pool_dedup_pass"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
