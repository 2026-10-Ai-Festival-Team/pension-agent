"""Build the zero-HCX three-record E2A neighboring supported smoke."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
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
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e2a_supported_answer_neighbors_preflight_v1.json"
NEIGHBOR_SOURCE_IDS = (
    "P49-2H-4D-E2-HOST-0005",  # DB benefit determination
    "P49-2H-4D-E2-HOST-0006",  # DC operation party
    "P49-2H-4D-E2-HOST-0008",  # ISA additional tax credit
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E2A neighbor artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_map = {row["remediation_request_id"]: row for row in source_rows}
    records: list[dict[str, Any]] = []
    for index, source_id in enumerate(NEIGHBOR_SOURCE_IDS, start=1):
        source = source_map.get(source_id)
        if source is None:
            raise ValueError(f"E2A neighbor source missing: {source_id}")
        if source["target_outcome"] != "supported_answer":
            raise ValueError("E2A neighbors must remain supported_answer")
        row = deepcopy(source)
        row.pop("supported_answer_completeness", None)
        row["e2a_neighbor_source_request_id"] = source_id
        row["remediation_request_id"] = f"P49-2H-4D-E2A-NEIGHBOR-{index:04d}"
        row["e2a_neighbor_status"] = "planned_zero_hcx"
        records.append(row)
    if len(records) != 3 or len({row["canonical_requirement"] for row in records}) != 3:
        raise AssertionError("E2A neighbor smoke requires exactly three distinct supported requirements")
    return records


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    synthetic: list[dict[str, Any]] = []
    for row in rows:
        try:
            if row.get("supported_answer_completeness") is not None:
                raise ValueError("target-only completeness binding leaked into neighbor")
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            if "[P49-2H-4D-E2A supported answer completeness — host-owned]" in caller_input["prompt"]:
                raise ValueError("target-only completeness prompt leaked into neighbor")
            question = render_host_question(adapted["semantic_request"], adapted["remediation_control"])
            semantic = semantic_question_findings(question, adapted["semantic_request"])
            register = bridge.register_surface_and_subject_findings(row, adapted, question)
            synthetic.append({
                "remediation_request_id": row["remediation_request_id"],
                "validation_status": "pass",
                "generation_status": "not_generated_e2a_neighbor_preflight",
                "question": question,
            })
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
    dedup = bridge.full_set_dedup_audit(current_pool, synthetic, bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions"))
    return {
        "stage": "P49-2H-4D-E2A Supported Answer Neighbor Smoke Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(current_pool),
        "requested": len(rows),
        "target_only_completeness_binding_leak": False,
        "preservation_renderer_semantic_pass": len(rows) - len(failures),
        "failures": failures,
        "full_set_dedup": dedup,
        "full_set_dedup_pass": collisions == 0,
        "live_execution_allowed": not failures and collisions == 0 and len(current_pool) == 435,
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
    rows = build_rows(read_jsonl(args.source_manifest))
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    current_pool, _ = register_builder.current_quality_pool()
    report = preflight(rows, semantic_rows, current_pool)
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": report["comparison_pool_pass"],
        "requested": report["requested"],
        "preflight_pass": report["preservation_renderer_semantic_pass"],
        "dedup_pass": report["full_set_dedup_pass"],
        "live_execution_allowed": report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
