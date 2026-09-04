"""Build the zero-HCX P49-2H-4D-E2 host-owned banmal renderer probe.

The additive artifact contains 24 deterministic final questions for preflight;
only its explicitly labelled 16 records may enter the live tranche.  Existing
E/E1 candidates are never part of the 435-PASS comparison pool or promoted.
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

from scripts import build_p49_2h_4d_e_register_tranche as register_builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_4d_e2_host_renderer import RENDERER_ID, render_host_question, validate_renderer_control
from scripts.run_p49_2h_full_adapter import semantic_question_findings


E_SOURCE_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_manifest_v1.jsonl"
BASE_MANIFEST = bridge.REMEDIATION_MANIFEST
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2_host_renderer_preflight_v1.json"

# tier, source artifact, source ID, register, deterministic family.
# The first 16 records form the only allowed live tranche: supported 8 and
# clarification 8, with four casual/terse rows inside each outcome.  The last
# eight rows are renderer-only coverage probes that never make an HCX call.
PLAN = (
    ("live", "E", "P49-2H-4D-E-REG-0001", "casual_banmal", "confirmation"),
    ("live", "E", "P49-2H-4D-E-REG-0002", "casual_banmal", "misconception"),
    ("live", "E", "P49-2H-4D-E-REG-0003", "casual_banmal", "planning"),
    ("live", "E", "P49-2H-4D-E-REG-0004", "casual_banmal", "evidence_check"),
    ("live", "E", "P49-2H-4D-E-REG-0011", "terse_banmal", "confirmation"),
    ("live", "E", "P49-2H-4D-E-REG-0012", "terse_banmal", "misconception"),
    ("live", "E", "P49-2H-4D-E-REG-0013", "terse_banmal", "planning"),
    ("live", "BASE", "P49-2H-4B-0005", "terse_banmal", "evidence_check"),
    ("live", "E", "P49-2H-4D-E-REG-0005", "casual_banmal", "direct"),
    ("live", "E", "P49-2H-4D-E-REG-0006", "casual_banmal", "confirmation"),
    ("live", "E", "P49-2H-4D-E-REG-0007", "casual_banmal", "planning"),
    ("live", "BASE", "P49-2H-4B-0270", "casual_banmal", "evidence_check"),
    ("live", "E", "P49-2H-4D-E-REG-0014", "terse_banmal", "evidence_check"),
    ("live", "E", "P49-2H-4D-E-REG-0015", "terse_banmal", "direct"),
    ("live", "E", "P49-2H-4D-E-REG-0016", "terse_banmal", "confirmation"),
    ("live", "E", "P49-2H-4D-E-REG-0017", "terse_banmal", "planning"),
    ("preflight_only", "BASE", "P49-2H-4B-0001", "casual_banmal", "direct"),
    ("preflight_only", "BASE", "P49-2H-4B-0002", "casual_banmal", "confirmation"),
    ("preflight_only", "BASE", "P49-2H-4B-0003", "casual_banmal", "planning"),
    ("preflight_only", "BASE", "P49-2H-4B-0004", "casual_banmal", "evidence_check"),
    ("preflight_only", "BASE", "P49-2H-4B-0271", "terse_banmal", "confirmation"),
    ("preflight_only", "BASE", "P49-2H-4B-0274", "terse_banmal", "direct"),
    ("preflight_only", "BASE", "P49-2H-4B-0287", "terse_banmal", "misconception"),
    ("preflight_only", "BASE", "P49-2H-4B-0288", "terse_banmal", "planning"),
)
FAMILY_TO_QUERY_FORM = {
    "direct": "direct",
    "confirmation": "confirmation",
    "misconception": "misconception",
    "planning": "conditional",
    "evidence_check": "evidence_limit",
}
LIVE_ALLOCATION = Counter({
    ("supported_answer", "casual_banmal"): 4,
    ("supported_answer", "terse_banmal"): 4,
    ("clarification_required", "casual_banmal"): 4,
    ("clarification_required", "terse_banmal"): 4,
})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2 renderer artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sources(e_rows: list[dict[str, Any]], base_rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    source_map = {
        "E": {row["remediation_request_id"]: row for row in e_rows},
        "BASE": {row["remediation_request_id"]: row for row in base_rows},
    }
    if any(len(source_map[name]) != len(rows) for name, rows in (("E", e_rows), ("BASE", base_rows))):
        raise ValueError("E2 source artifacts contain duplicate request IDs")
    return source_map


def build_rows(e_rows: list[dict[str, Any]], base_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_map = _sources(e_rows, base_rows)
    records: list[dict[str, Any]] = []
    for sequence, (tier, source_artifact, source_id, register, family) in enumerate(PLAN, start=1):
        source = source_map[source_artifact].get(source_id)
        if source is None:
            raise ValueError(f"E2 source row missing: {source_artifact}:{source_id}")
        row = deepcopy(source)
        if row["target_outcome"] == "bounded_answer":
            raise ValueError("E2 must exclude bounded_answer")
        row["e2_source_artifact"] = source_artifact
        row["e2_source_request_id"] = source_id
        row["remediation_request_id"] = f"P49-2H-4D-E2-HOST-{sequence:04d}"
        row["register"] = register
        row["query_form"] = FAMILY_TO_QUERY_FORM[family]
        row["noise_style"] = "none"
        row["host_question_renderer"] = {
            "renderer_id": RENDERER_ID,
            "family": family,
        }
        row["e2_execution_tier"] = tier
        row["e2_status"] = "planned_zero_hcx"
        records.append(row)
    if len(records) != 24 or len({row["remediation_request_id"] for row in records}) != 24:
        raise AssertionError("E2 must produce exactly 24 unique renderer records")
    live = [row for row in records if row["e2_execution_tier"] == "live"]
    if len(live) != 16 or Counter((row["target_outcome"], row["register"]) for row in live) != LIVE_ALLOCATION:
        raise AssertionError("E2 live tranche must be 8 supported + 8 clarification, 4 per register")
    if any(row["target_outcome"] == "bounded_answer" or row["noise_style"] != "none" for row in records):
        raise AssertionError("E2 renderer scope was widened")
    return records


def renderer_findings(row: dict[str, Any], adapted: dict[str, Any]) -> tuple[str, list[str]]:
    control = adapted["remediation_control"]
    semantic = adapted["semantic_request"]
    validate_renderer_control(control, adapted["contract_lane"])
    question = render_host_question(semantic, control)
    findings = semantic_question_findings(question, semantic)
    findings.extend(bridge.register_surface_and_subject_findings(row, adapted, question))
    if adapted["contract_lane"] == "clarification_required":
        compact = "".join(question.split())
        missing = [condition for condition in semantic["missing_conditions"] if "".join(condition.split()) not in compact]
        if missing:
            findings.append("host_renderer_missing_condition_omission:" + ",".join(missing))
    return question, sorted(set(findings))


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    synthetic_candidates: list[dict[str, Any]] = []
    rendered: list[dict[str, Any]] = []
    for row in rows:
        try:
            if row["target_outcome"] not in {"supported_answer", "clarification_required"}:
                raise ValueError("E2 lane outside approved scope")
            if row["register"] not in {"casual_banmal", "terse_banmal"} or row.get("noise_style") != "none":
                raise ValueError("E2 requires banmal renderer with noise_style=none")
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            question, semantic = renderer_findings(row, adapted)
            rendered.append({
                "remediation_request_id": row["remediation_request_id"],
                "coverage_cell": row["coverage_cell"],
                "target_outcome": row["target_outcome"],
                "register": row["register"],
                "family": row["host_question_renderer"]["family"],
                "execution_tier": row["e2_execution_tier"],
                "question": question,
            })
            synthetic_candidates.append({
                "remediation_request_id": row["remediation_request_id"],
                "validation_status": "pass",
                "generation_status": "not_generated_host_renderer_preflight",
                "question": question,
            })
            if preservation or diversity or boundary or semantic:
                failures.append({
                    "remediation_request_id": row["remediation_request_id"],
                    "preservation_findings": preservation,
                    "diversity_prompt_findings": diversity,
                    "field_boundary_prompt_findings": boundary,
                    "host_renderer_semantic_findings": semantic,
                })
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "renderer_error": str(exc)})
    dedup = bridge.full_set_dedup_audit(current_pool, synthetic_candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    collision_count = sum(
        len(dedup[key])
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    return {
        "stage": "P49-2H-4D-E2 Host-Owned Banmal Surface Renderer Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(current_pool),
        "requested": len(rows),
        "live_tranche_requested": sum(row["e2_execution_tier"] == "live" for row in rows),
        "preflight_only_requested": sum(row["e2_execution_tier"] == "preflight_only" for row in rows),
        "requested_by_lane_and_register": {
            f"{lane}:{register}": count
            for (lane, register), count in sorted(Counter((row["target_outcome"], row["register"]) for row in rows).items())
        },
        "host_rendered_questions": rendered,
        "preservation_renderer_semantic_pass": len(rows) - len(failures),
        "failures": failures,
        "renderer_full_set_dedup": dedup,
        "renderer_full_set_dedup_pass": collision_count == 0,
        "live_execution_allowed": not failures and collision_count == 0 and len(current_pool) == 435,
        "candidate_question_authority": "host_owned_renderer",
        "hcx_model_question_authority": "audit_only",
        "initial_e_candidate_promotion_held": True,
        "e1_candidate_promotion_held": True,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e-source-manifest", type=Path, default=E_SOURCE_MANIFEST)
    parser.add_argument("--base-manifest", type=Path, default=BASE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    current_pool, _ = register_builder.current_quality_pool()
    rows = build_rows(read_jsonl(args.e_source_manifest), read_jsonl(args.base_manifest))
    report = preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    report.update({
        "e_source_manifest": str(args.e_source_manifest),
        "e_source_manifest_sha256": hashlib.sha256(args.e_source_manifest.read_bytes()).hexdigest(),
        "base_manifest": str(args.base_manifest),
        "base_manifest_sha256": hashlib.sha256(args.base_manifest.read_bytes()).hexdigest(),
        "source_manifests_modified": False,
    })
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": report["comparison_pool_pass"],
        "requested": report["requested"],
        "live_tranche_requested": report["live_tranche_requested"],
        "preflight_pass": report["preservation_renderer_semantic_pass"],
        "dedup_pass": report["renderer_full_set_dedup_pass"],
        "live_execution_allowed": report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
