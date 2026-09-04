"""Build a small additive P49-2H-4D-E banmal-register tranche with zero HCX.

The tranche is intentionally limited to 20 records: ten ``casual_banmal`` and
ten ``terse_banmal``.  It uses the 435-PASS comparison pool, including the
approved D-D anchor promotion artifact, while leaving every prior manifest and
candidate artifact immutable.
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

from scripts import build_p49_2h_4d_bounded_targeted_v6 as v6
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS
from scripts.run_p49_2h_full_adapter import bounded_host_question, semantic_question_findings


MANIFEST = bridge.REMEDIATION_MANIFEST
PROMOTED_ANCHORS = ROOT / "evaluation/fine_tuning/p49_2h_4d_d_anchor_smoke_promoted_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_preflight_v1.json"
STYLE_LANE_QUOTAS = {
    "casual_banmal": {"supported_answer": 4, "clarification_required": 3, "bounded_answer": 3},
    "terse_banmal": {"supported_answer": 3, "clarification_required": 4, "bounded_answer": 3},
}
LANE_ORDER = ("supported_answer", "clarification_required", "bounded_answer")
ANCHOR_CELLS = frozenset({
    "D12-Q12-bounded_answer",
    "D17-Q17-bounded_answer",
    "D18-Q18-bounded_answer",
    "D20-Q12-bounded_answer",
})
# These are the already-established 4B controls.  They are balanced across
# the two banmal registers to prevent a single legacy context/form pair from
# deterministically colliding with the 435-PASS pool; no anchor-only profile
# dimension is used in this register experiment.
CONTROL_VARIANTS = (
    ("이전 신청 중", "confirmation", "short"),
    ("상담 전 확인", "misconception", "medium"),
    ("상품 비교 전 확인", "conditional", "short"),
    ("세액공제 계산 전", "numeric", "medium"),
    ("서류 준비 중", "direct", "short"),
    ("이직/퇴직 직후", "confirmation", "medium"),
    ("상담 전 확인", "conditional", "short"),
    ("상품 비교 전 확인", "numeric", "medium"),
    ("이전 신청 중", "confirmation", "medium"),
    ("서류 준비 중", "misconception", "medium"),
)


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite register-tranche artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def current_quality_pool() -> tuple[list[dict[str, Any]], set[str]]:
    immutable = [row for row in bridge.read_jsonl(bridge.COMPARISON_POOL) if row.get("validation_status") == "pass"]
    prior = v6.promoted_passes(v6.read_many(list(v6.DEFAULT_CANDIDATES)))
    anchors = [row for row in bridge.read_jsonl(PROMOTED_ANCHORS) if row.get("validation_status") == "pass"]
    if len(immutable) != 133 or len(prior) != 294 or len(anchors) != 8:
        raise ValueError(f"expected 133 + 294 + 8 quality pool; found {len(immutable)} + {len(prior)} + {len(anchors)}")
    request_ids = set(prior)
    anchor_ids = {row["remediation_request_id"] for row in anchors}
    if len(anchor_ids) != len(anchors) or request_ids & anchor_ids:
        raise ValueError("anchor promotion has duplicate remediation request IDs")
    pool = [*immutable, *prior.values(), *anchors]
    if len(pool) != 435:
        raise AssertionError("register tranche must use the fixed 435-PASS comparison pool")
    return pool, request_ids


def _distinct_sources(manifest_rows: list[dict[str, Any]], completed_ids: set[str]) -> dict[str, list[dict[str, Any]]]:
    """Choose distinct source cells, preferring unresolved rows.

    This is a wording-register experiment, not a claim on remaining raw
    manifest capacity.  Reusing a semantic source cell is valid for an
    additive style probe so long as the new candidate passes the complete
    435-PASS dedup comparison.  Anchor cells remain excluded to avoid mixing
    the two experiments.
    """
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_cells: set[tuple[str, str]] = set()
    for row in sorted(
        manifest_rows,
        key=lambda row: (row["remediation_request_id"] in completed_ids, row["remediation_request_id"]),
    ):
        key = row["target_outcome"], row["coverage_cell"]
        if (
            row["coverage_cell"] in ANCHOR_CELLS
            or key in seen_cells
        ):
            continue
        by_lane[row["target_outcome"]].append(row)
        seen_cells.add(key)
    if set(by_lane) != set(LANE_ORDER):
        raise ValueError("register tranche needs unresolved distinct source cells in every lane")
    # Bounded coverage has five factual domains but needs six rows.  Put one
    # repeat only after every available domain has been used once, avoiding a
    # same-domain D30 pair in the initial small tranche.
    bounded_unique: list[dict[str, Any]] = []
    bounded_repeats: list[dict[str, Any]] = []
    seen_domains: set[str] = set()
    for row in by_lane["bounded_answer"]:
        domain = row["coverage_cell"].split("-", 1)[0]
        (bounded_repeats if domain in seen_domains else bounded_unique).append(row)
        seen_domains.add(domain)
    by_lane["bounded_answer"] = [*bounded_unique, *bounded_repeats]
    return by_lane


def build_rows(manifest_rows: list[dict[str, Any]], completed_ids: set[str]) -> list[dict[str, Any]]:
    sources = _distinct_sources(manifest_rows, completed_ids)
    offsets = Counter()
    records: list[dict[str, Any]] = []
    sequence = 1
    for register, quotas in STYLE_LANE_QUOTAS.items():
        for lane in LANE_ORDER:
            for _ in range(quotas[lane]):
                index = offsets[lane]
                if index >= len(sources[lane]):
                    raise ValueError(f"insufficient distinct {lane} source cells for register tranche")
                source = deepcopy(sources[lane][index])
                offsets[lane] += 1
                source["register_source_manifest_request_id"] = source["remediation_request_id"]
                source["remediation_request_id"] = f"P49-2H-4D-E-REG-{sequence:04d}"
                source["register"] = register
                context_frame, query_form, length_band = CONTROL_VARIANTS[(sequence - 1) % len(CONTROL_VARIANTS)]
                source["context_frame"] = context_frame
                source["query_form"] = query_form
                source["length_band"] = length_band
                source["noise_style"] = "none"
                source["register_taxonomy_version"] = "P49-2H-register-v1"
                source["register_tranche_style"] = register
                source["register_tranche_status"] = "planned_zero_hcx"
                records.append(source)
                sequence += 1
    if len(records) != 20 or Counter(row["register"] for row in records) != Counter({"casual_banmal": 10, "terse_banmal": 10}):
        raise AssertionError("register tranche must contain exactly ten rows per banmal register")
    if len({row["coverage_cell"] for row in records}) != len(records):
        raise AssertionError("register tranche source coverage cells must be distinct")
    return records


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    bounded_virtual: list[dict[str, Any]] = []
    for row in rows:
        try:
            if row["register"] not in BANMAL_REGISTERS or row.get("noise_style") != "none":
                raise ValueError("register tranche must use banmal register with noise_style=none")
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            semantic = []
            if row["target_outcome"] == "bounded_answer":
                question = bounded_host_question(adapted["semantic_request"], adapted["remediation_control"])
                semantic = semantic_question_findings(question, adapted["semantic_request"])
                semantic.extend(bridge.register_surface_and_subject_findings(row, adapted, question))
                bounded_virtual.append({
                    "remediation_request_id": row["remediation_request_id"],
                    "validation_status": "pass",
                    "generation_status": "not_generated_register_tranche",
                    "question": question,
                })
            if preservation or diversity or boundary or semantic:
                failures.append({
                    "remediation_request_id": row["remediation_request_id"],
                    "preservation_findings": preservation,
                    "diversity_prompt_findings": diversity,
                    "field_boundary_prompt_findings": boundary,
                    "host_question_semantic_findings": sorted(set(semantic)),
                })
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    dedup = bridge.full_set_dedup_audit(current_pool, bounded_virtual, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    return {
        "stage": "P49-2H-4D-E Register Taxonomy Tranche Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(current_pool),
        "requested": len(rows),
        "requested_by_register": dict(Counter(row["register"] for row in rows)),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in rows)),
        "noise_style_counts": dict(Counter(row["noise_style"] for row in rows)),
        "preservation_prompt_and_host_question_pass": len(rows) - len(failures),
        "failures": failures,
        "bounded_host_question_dedup": dedup,
        "bounded_host_question_dedup_pass": collision_count == 0,
        "live_execution_allowed": not failures and collision_count == 0,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    pool, completed = current_quality_pool()
    manifest_rows = bridge.read_jsonl(args.manifest)
    rows = build_rows(manifest_rows, completed)
    preflight_report = preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    preflight_report.update({
        "source_manifest": str(args.manifest),
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
        "anchor_promotion_artifact": str(PROMOTED_ANCHORS),
        "anchor_promotion_sha256": hashlib.sha256(PROMOTED_ANCHORS.read_bytes()).hexdigest(),
    })
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(preflight_report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": preflight_report["comparison_pool_pass"],
        "requested": preflight_report["requested"],
        "requested_by_register": preflight_report["requested_by_register"],
        "preflight_pass": preflight_report["preservation_prompt_and_host_question_pass"],
        "dedup_pass": preflight_report["bounded_host_question_dedup_pass"],
        "live_execution_allowed": preflight_report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
