"""Audit register metadata before activating new P49-2H wording controls.

The audit is read-only and makes no HCX call.  It distinguishes legacy
baseline semantic-style labels from the explicit host-owned register that was
attached to promoted 4B remediation candidates, rather than pretending they
were one clean historic taxonomy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_p49_2h_4d_bounded_targeted_v6 as v6
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_register_taxonomy import (
    CANONICAL_REGISTERS,
    LEGACY_REGISTERS,
    REGISTER_ALLOCATION_CYCLE,
    REGISTER_RULES,
)


DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_register_taxonomy_preflight_v1.json"


def counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def report(
    baseline_rows: list[dict[str, Any]],
    promoted_rows: dict[str, dict[str, Any]],
    register_by_request: dict[str, str],
) -> dict[str, Any]:
    baseline_pass = [row for row in baseline_rows if row.get("validation_status") == "pass"]
    baseline_styles = [
        row.get("host_question_contract", {}).get("question_register", "missing")
        for row in baseline_pass
    ]
    promoted_registers: list[str] = []
    unmapped_promoted: list[str] = []
    for request_id in sorted(promoted_rows):
        value = register_by_request.get(request_id)
        if value is None:
            unmapped_promoted.append(request_id)
            value = "unmapped"
        promoted_registers.append(value)
    combined = [*baseline_styles, *promoted_registers]
    banmal_count = sum(value in {"casual_banmal", "terse_banmal"} for value in combined)
    return {
        "stage": "P49-2H Register Taxonomy Preflight",
        "external_hcx_calls": 0,
        "accepted_quality_pool": len(baseline_pass) + len(promoted_rows),
        "baseline_immutable_pass": len(baseline_pass),
        "promoted_remediation_pass": len(promoted_rows),
        "baseline_semantic_style_counts": counts(baseline_styles),
        "promoted_host_register_counts": counts(promoted_registers),
        "combined_legacy_metadata_counts": counts(combined),
        "unmapped_promoted_request_ids": unmapped_promoted,
        "observed_banmal_count": banmal_count,
        "observed_banmal_share": banmal_count / len(combined) if combined else 0.0,
        "new_register_taxonomy": list(CANONICAL_REGISTERS),
        "legacy_registers_retained_for_immutable_artifacts": list(LEGACY_REGISTERS),
        "new_additive_allocation_cycle": list(REGISTER_ALLOCATION_CYCLE),
        "new_additive_banmal_share": sum(
            value in {"casual_banmal", "terse_banmal"}
            for value in REGISTER_ALLOCATION_CYCLE
        ) / len(REGISTER_ALLOCATION_CYCLE),
        "new_register_rules_defined": sorted(REGISTER_RULES),
        "noise_style_activation": "not_enabled; register never implies typo or abbreviation",
        "existing_artifacts_modified": False,
        "hcx_execution_authorized": False,
    }


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite register-taxonomy audit: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-promoted-pass", type=int, default=294)
    args = parser.parse_args()

    manifest_rows = bridge.read_jsonl(bridge.REMEDIATION_MANIFEST)
    register_by_request = {row["remediation_request_id"]: row["register"] for row in manifest_rows}
    candidate_rows = v6.read_many(list(v6.DEFAULT_CANDIDATES))
    promoted = v6.promoted_passes(candidate_rows)
    if len(promoted) != args.expected_promoted_pass:
        parser.error(f"expected {args.expected_promoted_pass} promoted PASS candidates; found {len(promoted)}")
    baseline_rows = bridge.read_jsonl(bridge.COMPARISON_POOL)
    payload = report(baseline_rows, promoted, register_by_request)
    payload["source_manifest"] = str(bridge.REMEDIATION_MANIFEST)
    payload["source_manifest_sha256"] = hashlib.sha256(bridge.REMEDIATION_MANIFEST.read_bytes()).hexdigest()
    payload["source_manifest_modified"] = False
    write_new(args.output, payload)
    print(json.dumps({
        "external_hcx_calls": 0,
        "accepted_quality_pool": payload["accepted_quality_pool"],
        "observed_banmal_share": payload["observed_banmal_share"],
        "new_additive_banmal_share": payload["new_additive_banmal_share"],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
