"""Classify immutable P50-v2 failures by runtime root cause (zero HCX)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/fresh_p50_final_holdout_execution_v2.json"
OUT = ROOT / "evaluation/fresh_p50_v2_failure_adjudication_v1.json"


def _primary(output: dict) -> tuple[str, list[str], bool, str | None]:
    record_id = output["id"]
    failures = set(output["failure_classes"])
    criteria = next((row.get("criteria", {}) for row in _rows() if row["id"] == record_id), {})
    # This is a static contract inconsistency: a single-subject IRP lane is
    # asked to prove a general-account comparison through just one requirement.
    if record_id == "P50V2-023":
        return "other_new_runtime_failure", sorted(failures), False, "expected_requirement_is_not_a_complete_single-subject comparison contract"
    if criteria.get("prompt_injection_resistance") and output["actual_outcome"] != "safe_block":
        return "other_new_runtime_failure", sorted(failures), True, None
    if criteria.get("future_value_boundary") and output["actual_outcome"] != "bounded_answer":
        return "future_boundary_misclassification", sorted(failures), True, None
    if output["expected_outcome"] == "clarification_required" and output["actual_outcome"] != "clarification_required":
        return "clarification_policy_error", sorted(failures), True, None
    if output.get("generation_error"):
        return "citation_provenance_validation", sorted(failures), True, None
    if "field_confusion" in failures:
        return "field_confusion", sorted(failures), True, None
    if "required_fact_omission" in failures:
        return "required_fact_omission", sorted(failures), True, None
    if "selector_unresolved" in failures:
        return "selector_natural_language_unresolved", sorted(failures), True, None
    return "other_new_runtime_failure", sorted(failures), True, None


def _rows() -> list[dict]:
    path = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v2.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    execution = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = []
    for output in execution["outputs"]:
        if output["strict_pass"]:
            continue
        primary, secondary, runtime_valid, invalid_reason = _primary(output)
        records.append({
            "record_id": output["id"], "question": output["question"],
            "expected_outcome": output["expected_outcome"], "actual_outcome": output["actual_outcome"],
            "selected_subject": output["actual_active_subject"],
            "selected_requirement": output["actual_requirements"],
            "selected_evidence": output["cited_chunk_ids"],
            "primary_root_cause": primary, "secondary_findings": secondary,
            "genuine_runtime_failure": runtime_valid, "benchmark_contract_invalid_reason": invalid_reason,
        })
    counts: dict[str, int] = {}
    for item in records:
        counts[item["primary_root_cause"]] = counts.get(item["primary_root_cause"], 0) + 1
    payload = {
        "experiment": "Fresh P50 v2 immutable failure adjudication", "hcx_calls": 0,
        "source_execution": str(SOURCE.relative_to(ROOT)), "strict_failure_count": len(records),
        "genuine_runtime_failure_count": sum(item["genuine_runtime_failure"] for item in records),
        "benchmark_contract_invalid_count": sum(not item["genuine_runtime_failure"] for item in records),
        "primary_root_cause_counts": dict(sorted(counts.items())), "records": records,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("strict_failure_count", "genuine_runtime_failure_count", "benchmark_contract_invalid_count", "primary_root_cause_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
