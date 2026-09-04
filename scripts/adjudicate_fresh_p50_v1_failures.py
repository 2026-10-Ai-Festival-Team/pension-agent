"""HCX-zero adjudication of immutable Fresh P50 v1 failures."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "evaluation/fresh_p50_final_holdout_execution_v1.json"
OUT = ROOT / "evaluation/fresh_p50_v1_failure_adjudication_v1.json"

# These reasons are about the benchmark's frozen contract, never a rewrite of
# its result.  IDs omitted here are genuine runtime failures.
INVALID = {
    "P50-007": "supported_expected_without_resolvable_single_subject",
    "P50-008": "supported_expected_without_resolvable_single_subject",
    "P50-009": "oracle_requires_literal_term_despite_semantically_equivalent_answer",
    "P50-011": "forbidden_claim_oracle_matches_a_correct_negation",
    "P50-016": "required_facts_not_fully_present_in_selected_evidence",
    "P50-017": "supported_expected_without_resolvable_single_subject",
    "P50-020": "supported_expected_without_resolvable_single_subject",
    "P50-021": "supported_expected_without_resolvable_single_subject",
    "P50-027": "question_asks_management_fee_but_expected_requirement_is_total_fee",
    "P50-028": "forbidden_claim_oracle_not_a_semantic_expansion_check",
    "P50-031": "supported_expected_without_resolvable_single_subject",
    "P50-032": "supported_expected_without_resolvable_single_subject_and_character_level_required_fact",
    "P50-033": "supported_expected_without_resolvable_single_subject",
    "P50-034": "supported_expected_without_resolvable_single_subject_and_character_level_required_fact",
    "P50-038": "forbidden_claim_oracle_matches_a_correct_negation",
    "P50-040": "forbidden_claim_oracle_matches_safe_refusal_text",
    "P50-042": "supported_expected_without_resolvable_single_subject",
    "P50-044": "supported_expected_for_multi_subject_comparison_on_single_subject_path",
    "P50-045": "supported_expected_for_multi_subject_comparison_on_single_subject_path_and_character_level_required_fact",
    "P50-046": "supported_expected_without_resolvable_single_subject",
    "P50-047": "supported_expected_for_multi_subject_comparison_on_single_subject_path_and_character_level_required_fact",
}

CLASS = {
    "P50-004": "required_fact_omission",
    "P50-024": "future_boundary_failure",
    "P50-025": "required_fact_omission",
    "P50-029": "selector_natural_language_unresolved",
    "P50-035": "selector_natural_language_unresolved",
    "P50-039": "future_boundary_failure",
    "P50-041": "prompt_injection_failure",
    "P50-043": "selector_natural_language_unresolved",
    "P50-048": "selector_natural_language_unresolved",
    "P50-049": "future_boundary_failure",
}


def main():
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    records = []
    for output in execution["outputs"]:
        if not output["failure_classes"]:
            continue
        invalid_reason = INVALID.get(output["id"])
        runtime_class = None if invalid_reason else CLASS.get(output["id"], "other_genuine_failure")
        records.append({
            "record_id": output["id"], "expected_outcome": output["expected_outcome"],
            "actual_outcome": output["actual_outcome"],
            "strict_failure_classes": output["failure_classes"],
            "benchmark_valid": invalid_reason is None,
            "benchmark_invalid_reason": invalid_reason,
            "genuine_runtime_failure": runtime_class is not None,
            "runtime_failure_class": runtime_class,
        })
    payload = {
        "experiment": "Fresh P50 v1 Failure Adjudication", "hcx_calls": 0,
        "source_execution": str(EXECUTION.relative_to(ROOT)), "source_immutable": True,
        "strict_failure_count": len(records),
        "benchmark_invalid_count": sum(not item["benchmark_valid"] for item in records),
        "genuine_runtime_failure_count": sum(item["genuine_runtime_failure"] for item in records),
        "runtime_failure_class_counts": {
            key: sum(item["runtime_failure_class"] == key for item in records)
            for key in sorted({item["runtime_failure_class"] for item in records if item["runtime_failure_class"]})
        },
        "records": records,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("strict_failure_count", "benchmark_invalid_count", "genuine_runtime_failure_count", "runtime_failure_class_counts")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
