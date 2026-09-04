"""Close F's logical 50-record quality gate using its one F1A replacement."""
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

from scripts import build_p49_2h_4d_f_register_additive as builder
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts import run_p49_2h_4d_f_register_additive as runner
from scripts import run_p49_2h_4d_f1a_generation_retry as retry


DEFAULT_OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_f_register_additive_closure_v1.json"


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite F register closure artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def report() -> dict[str, Any]:
    selected = bridge.read_jsonl(runner.DEFAULT_MANIFEST)
    traces = bridge.read_jsonl(runner.DEFAULT_TRACE_OUTPUT)
    candidates = bridge.read_jsonl(runner.DEFAULT_CANDIDATE_OUTPUT)
    retry_trace = bridge.read_jsonl(retry.DEFAULT_TRACE)
    retry_candidates = bridge.read_jsonl(retry.DEFAULT_CANDIDATES)
    if len(retry_trace) != 1 or len(retry_candidates) != 1:
        raise ValueError("F closure requires one F1A trace and candidate")
    original_trace = next(row for row in traces if row["remediation_request_id"] == retry.SOURCE_REQUEST_ID)
    if original_trace.get("generation_status") != "generation_exhausted":
        raise ValueError("F closure can only replace the original exhausted F record")
    replacement_trace, replacement = retry_trace[0], retry_candidates[0]
    if replacement.get("validation_status") != "pass":
        raise ValueError("F1A replacement must be a validated PASS")
    source_row = next(row for row in selected if row["remediation_request_id"] == retry.SOURCE_REQUEST_ID)
    retry_row = retry.build_row(selected, traces)
    identity_fields = ("coverage_cell", "target_outcome", "canonical_requirement", "subject", "evidence_chunk_ids", "source_ids", "context_frame", "query_form", "register", "length_band", "host_question_renderer")
    identity_mismatches = [field for field in identity_fields if source_row.get(field) != retry_row.get(field)]
    if identity_mismatches or replacement.get("question") != builder.rendered_question(source_row, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS))[1]:
        raise ValueError("F1A replacement changed the original host-owned F identity")
    # The closure audit views F1A as the logical completion of F-0022 while
    # retaining the physical retry ID in the lineage block above.  No source
    # artifact is edited.
    logical_replacement_trace = deepcopy(replacement_trace)
    logical_replacement_trace["physical_retry_request_id"] = retry.RETRY_REQUEST_ID
    logical_replacement_trace["remediation_request_id"] = retry.SOURCE_REQUEST_ID
    logical_replacement = deepcopy(replacement)
    logical_replacement["physical_retry_request_id"] = retry.RETRY_REQUEST_ID
    logical_replacement["remediation_request_id"] = retry.SOURCE_REQUEST_ID
    logical_traces = [row for row in traces if row["remediation_request_id"] != retry.SOURCE_REQUEST_ID] + [logical_replacement_trace]
    logical_candidates = candidates + [logical_replacement]
    pool = builder.current_quality_pool()
    audit = runner.audit(selected, logical_traces, logical_candidates, pool)
    return {
        "stage": "P49-2H-4D-F Logical Register Additive Quality Gate Closure via F1A",
        "external_hcx_calls": 0,
        "comparison_pool_before": len(pool),
        "logical_f_candidate_count": len(logical_candidates),
        "logical_f_candidate_pass": sum(row.get("validation_status") == "pass" for row in logical_candidates),
        "f1a_replacement": {
            "original_f_request_id": retry.SOURCE_REQUEST_ID,
            "replacement_f1a_request_id": retry.RETRY_REQUEST_ID,
            "host_owned_identity_preserved": not identity_mismatches,
            "original_generation_status": original_trace["generation_status"],
            "replacement_validation_status": replacement["validation_status"],
        },
        "bridge_schema_hydration_validator_50_of_50": audit["bridge_healthy"],
        "quality_metrics": audit["quality_metrics"],
        "validation_findings": audit["validation_findings"],
        "new_failure_classes": audit["new_failure_classes"],
        "cumulative_full_set_dedup": audit["cumulative_full_set_dedup"],
        "cumulative_full_set_dedup_pass": audit["cumulative_full_set_dedup_pass"],
        "register_metrics": audit["register_metrics"],
        "register_additive_quality_go": audit["register_additive_quality_go"],
        "promotion_eligible_pass_count": len(logical_candidates) if audit["register_additive_quality_go"] else 0,
        "promotion_executed": False,
        "comparison_pool_after": len(pool),
        "batch_07_execution_allowed": audit["register_additive_quality_go"],
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = report()
    write_new(args.output, result)
    print(json.dumps({
        "external_hcx_calls": 0,
        "logical_f_candidate_pass": result["logical_f_candidate_pass"],
        "register_additive_quality_go": result["register_additive_quality_go"],
        "batch_07_execution_allowed": result["batch_07_execution_allowed"],
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
