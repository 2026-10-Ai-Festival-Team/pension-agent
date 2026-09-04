"""Build the zero-HCX P49-2H-4D-E1 supported/clarification banmal retest.

E1 is deliberately a small, independent twelve-record smoke.  It reuses the
initial register tranche's difficult model-authored source cells, but it does
not reuse or promote any initial E candidate.  The fixed comparison pool
therefore remains the 435 accepted-quality records from before that tranche.
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
from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS


SOURCE_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_e_register_tranche_manifest_v1.jsonl"
DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_manifest_v1.jsonl"
DEFAULT_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_e1_banmal_binding_retest_preflight_v1.json"
DEFAULT_BINDING_VERSION = "P49-2H-4D-E1-subject-surface-v2"

# Reuse the model-authored paths that exposed the E failure, including a small
# number of prior passes as regression controls.  All twelve source records
# remain immutable; this manifest gets fresh remediation request IDs.
RETEST_SOURCE_IDS = (
    "P49-2H-4D-E-REG-0001",  # casual / supported / prior subject loss
    "P49-2H-4D-E-REG-0002",  # casual / supported / prior subject loss
    "P49-2H-4D-E-REG-0004",  # casual / supported / prior pass control
    "P49-2H-4D-E-REG-0005",  # casual / clarification / prior subject loss
    "P49-2H-4D-E-REG-0006",  # casual / clarification / both binding failures
    "P49-2H-4D-E-REG-0007",  # casual / clarification / prior surface drift
    "P49-2H-4D-E-REG-0011",  # terse / supported / prior surface drift
    "P49-2H-4D-E-REG-0012",  # terse / supported / prior pass control
    "P49-2H-4D-E-REG-0013",  # terse / supported / prior pass control
    "P49-2H-4D-E-REG-0014",  # terse / clarification / both binding failures
    "P49-2H-4D-E-REG-0015",  # terse / clarification / prior subject loss
    "P49-2H-4D-E-REG-0016",  # terse / clarification / prior surface drift
)
EXPECTED_ALLOCATION = Counter({
    ("supported_answer", "casual_banmal"): 3,
    ("clarification_required", "casual_banmal"): 3,
    ("supported_answer", "terse_banmal"): 3,
    ("clarification_required", "terse_banmal"): 3,
})


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite E1 binding-retest artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_rows(source_rows: list[dict[str, Any]], *, binding_version: str = DEFAULT_BINDING_VERSION) -> list[dict[str, Any]]:
    by_id = {row["remediation_request_id"]: row for row in source_rows}
    if len(by_id) != len(source_rows):
        raise ValueError("register source manifest contains duplicate request IDs")
    missing = [request_id for request_id in RETEST_SOURCE_IDS if request_id not in by_id]
    if missing:
        raise ValueError("E1 retest source IDs missing from immutable E manifest: " + ", ".join(missing))

    rows: list[dict[str, Any]] = []
    for sequence, source_request_id in enumerate(RETEST_SOURCE_IDS, start=1):
        row = deepcopy(by_id[source_request_id])
        if row["target_outcome"] == "bounded_answer" or row["register"] not in BANMAL_REGISTERS:
            raise ValueError(f"invalid E1 source row: {source_request_id}")
        row["banmal_retest_source_request_id"] = source_request_id
        row["remediation_request_id"] = f"P49-2H-4D-E1-BANMAL-{sequence:04d}"
        row["register_binding_version"] = binding_version
        row["register_tranche_status"] = "binding_retest_planned_zero_hcx"
        rows.append(row)

    allocation = Counter((row["target_outcome"], row["register"]) for row in rows)
    if len(rows) != 12 or allocation != EXPECTED_ALLOCATION:
        raise AssertionError(f"E1 needs supported/clarification 3x2 per register; found {dict(allocation)}")
    if any(row.get("noise_style") != "none" for row in rows):
        raise AssertionError("E1 must preserve noise_style=none")
    if len({row["coverage_cell"] for row in rows}) != len(rows):
        raise AssertionError("E1 source coverage cells must be distinct")
    return rows


def binding_prompt_findings(row: dict[str, Any], caller_input: dict[str, Any]) -> list[str]:
    """Independently prove E1's two new host-owned prompt controls are active."""
    prompt = caller_input["prompt"]
    markers = [
        f"banmal_subject_binding: subject={row['subject']}",
        f"banmal_register_surface={row['register']}:",
        f"banmal_final_question_check: subject={row['subject']}; register={row['register']}",
        "‘그거’, ‘이거’, ‘그 상품’, ‘그건’",
        "존댓말(~요?, ~습니다?)과 서술형 종결은 금지합니다.",
    ]
    if row["register"] == "casual_banmal":
        markers.append("~야?, ~거야?, ~맞아?, ~되는 거야?")
    else:
        markers.append("~임?, ~맞지?, ~됨?, ~몰라?, ~있음?")
    return [f"banmal_binding_prompt_missing:{marker.split(':', 1)[0]}" for marker in markers if marker not in prompt]


def preflight(rows: list[dict[str, Any]], semantic_rows: list[dict[str, Any]], current_pool: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        try:
            if row["target_outcome"] == "bounded_answer":
                raise ValueError("bounded_answer is explicitly excluded from E1")
            if row["register"] not in BANMAL_REGISTERS or row.get("noise_style") != "none":
                raise ValueError("E1 requires banmal register with noise_style=none")
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller_input = bridge.caller_input_for(adapted, [candidate["question"] for candidate in current_pool])
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller_input)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller_input)
            binding = binding_prompt_findings(row, caller_input)
            if preservation or diversity or boundary or binding:
                failures.append({
                    "remediation_request_id": row["remediation_request_id"],
                    "preservation_findings": preservation,
                    "diversity_prompt_findings": diversity,
                    "field_boundary_prompt_findings": boundary,
                    "banmal_binding_prompt_findings": binding,
                })
        except (KeyError, ValueError) as exc:
            failures.append({"remediation_request_id": row["remediation_request_id"], "adapter_error": str(exc)})
    return {
        "stage": "P49-2H-4D-E1 Banmal Subject and Surface Binding Retest Preflight",
        "external_hcx_calls": 0,
        "comparison_pool_pass": len(current_pool),
        "requested": len(rows),
        "requested_by_register": dict(Counter(row["register"] for row in rows)),
        "requested_by_lane": dict(Counter(row["target_outcome"] for row in rows)),
        "requested_by_lane_and_register": {
            f"{lane}:{register}": count
            for (lane, register), count in sorted(Counter((row["target_outcome"], row["register"]) for row in rows).items())
        },
        "noise_style_counts": dict(Counter(row["noise_style"] for row in rows)),
        "preservation_and_binding_prompt_pass": len(rows) - len(failures),
        "failures": failures,
        "live_execution_allowed": not failures and len(current_pool) == 435,
        "initial_e_candidate_promotion_held": True,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--binding-version", default=DEFAULT_BINDING_VERSION)
    args = parser.parse_args()

    current_pool, _ = register_builder.current_quality_pool()
    rows = build_rows(read_jsonl(args.source_manifest), binding_version=args.binding_version)
    report = preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), current_pool)
    report.update({
        "source_manifest": str(args.source_manifest),
        "source_manifest_sha256": hashlib.sha256(args.source_manifest.read_bytes()).hexdigest(),
        "source_manifest_modified": False,
        "comparison_pool_semantics": "435 only; initial E tranche candidates remain promotion_hold",
    })
    write_new(args.output, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    write_new(args.audit_output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "external_hcx_calls": 0,
        "comparison_pool_pass": report["comparison_pool_pass"],
        "requested": report["requested"],
        "preflight_pass": report["preservation_and_binding_prompt_pass"],
        "live_execution_allowed": report["live_execution_allowed"],
        "output": str(args.output),
        "audit_output": str(args.audit_output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
