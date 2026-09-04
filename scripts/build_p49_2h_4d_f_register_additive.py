"""Build a 50-row, zero-HCX additive register tranche from the 451-PASS pool.

The exact canonical five-register allocation has 10 / 50 banmal rows.  Final
questions are host-rendered: F renderer for supported/clarification and the
existing bounded renderer for bounded.  This builder is additive and never
modifies the frozen 4B manifest or prior E2 artifacts.
"""
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

from scripts import build_p49_2h_4d_e_register_tranche as e_builder
from scripts import promote_p49_2h_4d_e2_quality_gate as e2_promotion
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_4d_f_host_renderer import RENDERER_ID, render_host_question, surface_findings
from scripts.p49_2h_register_taxonomy import CANONICAL_REGISTERS, register_for_index
from scripts.run_p49_2h_full_adapter import bounded_host_question, semantic_question_findings


SOURCE_MANIFEST = bridge.REMEDIATION_MANIFEST
PROMOTED_E2 = e2_promotion.DEFAULT_OUTPUT
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_preflight_v1.json"
TRANCHE_SIZE = 50
LANE_TARGETS = {"supported_answer": 24, "clarification_required": 16, "bounded_answer": 10}
FAMILY_CYCLE = ("direct", "confirmation", "misconception", "planning", "evidence_check")
CONTROL_CYCLE = (
    ("이직/퇴직 직후", "short"),
    ("이전 신청 중", "medium"),
    ("상담 전 확인", "short"),
    ("상품 비교 전 확인", "medium"),
    ("세액공제 계산 전", "short"),
    ("서류 준비 중", "medium"),
)
FAMILY_QUERY_FORM = {
    "direct": "direct",
    "confirmation": "confirmation",
    "misconception": "misconception",
    "planning": "conditional",
    "evidence_check": "evidence_limit",
}
# The E2A binding is deliberately not generalized by this register experiment.
# It stays scoped to its one IRP ETF target as proven by the neighbor smoke.
EXCLUDED_SUPPORTED_REQUIREMENTS = frozenset({"retirement_pension.ETF.direct_trade_scope"})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite F register-additive artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def current_quality_pool() -> list[dict[str, Any]]:
    base_pool, _ = e_builder.current_quality_pool()
    promoted = [row for row in bridge.read_jsonl(PROMOTED_E2) if row.get("validation_status") == "pass"]
    if len(base_pool) != 435 or len(promoted) != 16:
        raise ValueError(f"F register tranche requires 435 + 16 pool; found {len(base_pool)} + {len(promoted)}")
    # The immutable 133-PASS pool predates remediation IDs; its candidate ID
    # is the stable identity used by the existing full-set dedup route.
    ids = [row.get("remediation_request_id") or row.get("candidate_id") or row.get("full_request_id") for row in [*base_pool, *promoted]]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("451-PASS comparison pool has duplicate or missing request IDs")
    return [*base_pool, *promoted]


def _lane_plan() -> tuple[str, ...]:
    """Use the canonical register cycle while spreading the two banmal styles."""
    banmal_lanes = {
        8: "supported_answer", 9: "clarification_required",
        18: "supported_answer", 19: "clarification_required",
        28: "supported_answer", 29: "bounded_answer",
        38: "clarification_required", 39: "bounded_answer",
        48: "clarification_required", 49: "bounded_answer",
    }
    # The remaining 40 slots are intentionally supported/clarification heavy;
    # bounded remains represented without treating known duplicate-heavy cells
    # as a capacity solution.
    normal_lanes = iter(
        ["supported_answer"] * 21
        + ["clarification_required"] * 12
        + ["bounded_answer"] * 7
    )
    result = tuple(banmal_lanes[index] if index in banmal_lanes else next(normal_lanes) for index in range(TRANCHE_SIZE))
    if Counter(result) != Counter(LANE_TARGETS):
        raise AssertionError("F register lane allocation drifted")
    return result


def _source_allowed(source: dict[str, Any], lane: str) -> bool:
    if source["target_outcome"] != lane:
        return False
    if lane == "supported_answer":
        return (
            source.get("canonical_requirement") in __import__("scripts.p49_2h_4d_f_host_renderer", fromlist=["SUPPORTED_TOPICS"]).SUPPORTED_TOPICS
            and source.get("canonical_requirement") not in EXCLUDED_SUPPORTED_REQUIREMENTS
        )
    # Keep the human-anchor saturation cells out of this register-only probe.
    return source["coverage_cell"] not in e_builder.ANCHOR_CELLS


def _row_from_source(
    source: dict[str, Any], sequence: int, lane: str, register: str, *, surface_variant_offset: int = 0,
) -> dict[str, Any]:
    row = deepcopy(source)
    context_frame, length_band = CONTROL_CYCLE[(sequence - 1 + surface_variant_offset) % len(CONTROL_CYCLE)]
    family = FAMILY_CYCLE[(sequence - 1 + surface_variant_offset) % len(FAMILY_CYCLE)]
    row["register_source_manifest_request_id"] = source["remediation_request_id"]
    row["remediation_request_id"] = f"P49-2H-4D-F-REG-{sequence:04d}"
    row["register"] = register
    row["context_frame"] = context_frame
    row["query_form"] = FAMILY_QUERY_FORM[family]
    row["length_band"] = length_band
    row["noise_style"] = "none"
    row["register_taxonomy_version"] = "P49-2H-register-v1"
    row["register_additive_stage"] = "P49-2H-4D-F"
    row["register_additive_status"] = "planned_zero_hcx"
    row["register_surface_variant_offset"] = surface_variant_offset
    if lane in {"supported_answer", "clarification_required"}:
        row["host_question_renderer"] = {"renderer_id": RENDERER_ID, "family": family}
    else:
        row.pop("host_question_renderer", None)
    row.pop("supported_answer_completeness", None)
    return row


def rendered_question(row: dict[str, Any], semantic_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str, list[str]]:
    adapted = bridge.adapt_remediation_record(row, semantic_rows)
    semantic = adapted["semantic_request"]
    if row["target_outcome"] == "bounded_answer":
        question = bounded_host_question(semantic, adapted["remediation_control"])
        findings = semantic_question_findings(question, semantic)
        findings.extend(bridge.register_surface_and_subject_findings(row, adapted, question))
    else:
        question = render_host_question(semantic, adapted["remediation_control"])
        findings = semantic_question_findings(question, semantic)
        findings.extend(surface_findings(question, semantic, adapted["remediation_control"]))
    return adapted, question, sorted(set(findings))


def _collision_count(audit: dict[str, Any]) -> int:
    return sum(len(audit[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))


def build_rows(source_rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_plan = _lane_plan()
    source_by_lane = {
        lane: [row for row in source_rows if _source_allowed(row, lane)]
        for lane in LANE_TARGETS
    }
    if any(not source_by_lane[lane] for lane in LANE_TARGETS):
        raise ValueError("F register tranche cannot find an eligible source in every lane")
    selected: list[dict[str, Any]] = []
    synthetic: list[dict[str, Any]] = []
    used_source_ids: set[str] = set()
    offsets = Counter()
    for index, lane in enumerate(lane_plan):
        sequence, register = index + 1, register_for_index(index)
        if register not in CANONICAL_REGISTERS:
            raise AssertionError("F register allocation contains an unknown register")
        candidates = source_by_lane[lane]
        found = None
        for step in range(len(candidates)):
            source = candidates[(offsets[lane] + step) % len(candidates)]
            if source["remediation_request_id"] in used_source_ids:
                continue
            for surface_variant_offset in range(len(CONTROL_CYCLE)):
                row = _row_from_source(
                    source, sequence, lane, register, surface_variant_offset=surface_variant_offset,
                )
                try:
                    adapted, question, semantic = rendered_question(row, semantic_rows)
                    caller = bridge.caller_input_for(adapted, [candidate["question"] for candidate in [*pool, *synthetic]])
                    failures = (
                        bridge.preservation_findings(row, adapted)
                        + bridge.diversity_prompt_findings(row, caller)
                        + bridge.field_boundary_prompt_findings(row, adapted, caller)
                        + semantic
                    )
                    if failures:
                        continue
                    virtual = {"remediation_request_id": row["remediation_request_id"], "validation_status": "pass", "question": question}
                    dedup = bridge.full_set_dedup_audit(pool, [*synthetic, virtual], bridge.read_jsonl(bridge.FROZEN_SEED))
                    if _collision_count(dedup):
                        continue
                except (KeyError, ValueError):
                    continue
                found = (row, virtual, step)
                break
            if found is not None:
                break
        if found is None:
            raise ValueError(f"F register tranche could not allocate a clean {lane} row for slot {sequence}")
        row, virtual, step = found
        selected.append(row)
        synthetic.append(virtual)
        used_source_ids.add(row["register_source_manifest_request_id"])
        offsets[lane] += step + 1
    register_counts = Counter(row["register"] for row in selected)
    if len(selected) != TRANCHE_SIZE or Counter(row["target_outcome"] for row in selected) != Counter(LANE_TARGETS):
        raise AssertionError("F register tranche size or lane allocation drifted")
    if register_counts != Counter({"formal": 15, "polite": 15, "conversational": 10, "casual_banmal": 5, "terse_banmal": 5}):
        raise AssertionError("F register tranche does not preserve the canonical 20-percent banmal allocation")
    return selected


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    virtual: list[dict[str, Any]] = []
    for row in rows:
        try:
            adapted, question, semantic = rendered_question(row, semantic_rows)
            caller = bridge.caller_input_for(adapted, [candidate["question"] for candidate in pool])
            findings = {
                "preservation_findings": bridge.preservation_findings(row, adapted),
                "diversity_prompt_findings": bridge.diversity_prompt_findings(row, caller),
                "field_boundary_prompt_findings": bridge.field_boundary_prompt_findings(row, adapted, caller),
                "host_question_findings": semantic,
            }
            if any(findings.values()):
                failures.append({"remediation_request_id": row["remediation_request_id"], **findings})
            virtual.append({"remediation_request_id": row["remediation_request_id"], "validation_status": "pass", "question": question})
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row.get("remediation_request_id"), "preflight_error": str(exc)})
    dedup = bridge.full_set_dedup_audit(pool, virtual, bridge.read_jsonl(bridge.FROZEN_SEED))
    return {
        "stage": "P49-2H-4D-F Register Taxonomy Additive Tranche Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(pool),
        "requested": len(rows),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in rows)),
        "requested_by_register": dict(Counter(row["register"] for row in rows)),
        "banmal_share": sum(row["register"] in {"casual_banmal", "terse_banmal"} for row in rows) / len(rows),
        "host_renderer_by_lane": {
            "supported_answer": RENDERER_ID,
            "clarification_required": RENDERER_ID,
            "bounded_answer": "existing_bounded_host_renderer",
        },
        "preservation_renderer_semantic_pass": len(rows) - len(failures),
        "failures": failures,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": _collision_count(dedup) == 0,
        "live_execution_allowed": not failures and _collision_count(dedup) == 0 and len(pool) == 451,
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
    pool = current_quality_pool()
    source_rows = bridge.read_jsonl(args.source_manifest)
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    rows = build_rows(source_rows, semantic_rows, pool)
    report = preflight(rows, semantic_rows, pool)
    report.update({
        "source_manifest": str(args.source_manifest),
        "source_manifest_sha256": hashlib.sha256(args.source_manifest.read_bytes()).hexdigest(),
        "e2_promotion_artifact": str(PROMOTED_E2),
        "e2_promotion_sha256": hashlib.sha256(PROMOTED_E2.read_bytes()).hexdigest(),
        "source_artifacts_modified": False,
    })
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": report["comparison_pool_pass"],
        "requested": report["requested"],
        "requested_by_register": report["requested_by_register"],
        "dedup_pass": report["full_set_dedup_pass"],
        "live_execution_allowed": report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
