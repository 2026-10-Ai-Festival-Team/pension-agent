"""Re-score frozen P40 selector outputs after resolver-only changes; no HCX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver


HOLDOUT = ROOT / "question_bank/holdouts/p40_scope_reference_holdout.jsonl"
FROZEN_OUTPUT = ROOT / "evaluation/p40_scope_reference_holdout.json"
OUTPUT = ROOT / "evaluation/p40b_scope_reference_regression.json"


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    rows = _rows()
    frozen = json.loads(FROZEN_OUTPUT.read_text(encoding="utf-8"))
    selector_outputs = {item["id"]: item for item in frozen["outputs"]}
    resolver, binder = ScopeReferenceResolver(), DeterministicBinder()
    details = []
    unresolved_total = unresolved_correct = unsafe_ambiguous = binding_errors = 0
    resolved_total = resolved_correct = 0
    for row in rows:
        selected = tuple(selector_outputs[row["id"]]["selected_requirements"])
        resolution = resolver.resolve(row["question"])
        binding = binder.bind(row["question"], resolution, selected)
        if row["expected_reference_behavior"] == "unresolved":
            unresolved_total += 1
            correct = bool(resolution.unresolved_references) and all(item.status == "unresolved_reference" for item in binding.bindings)
            unresolved_correct += int(correct)
            unsafe_ambiguous += int(not correct)
            binding_error = not correct
        else:
            resolved_total += 1
            correct = list(resolution.active_subjects) == row["expected_active_subjects"] and not resolution.unresolved_references
            resolved_correct += int(correct)
            binding_error = bool(binding.scope_conflicts or binding.unresolved_references or any(item.status not in {"bound", "bound_comparison"} for item in binding.bindings))
        binding_errors += int(binding_error)
        details.append({"id": row["id"], "selected_requirements": list(selected), "resolution": resolution.as_dict(), "binding": binding.as_dict(), "reference_correct": correct, "binding_error": binding_error})
    payload = {
        "experiment": "P40-B Scope/Reference Regression",
        "input": {
            "holdout": str(HOLDOUT.relative_to(ROOT)),
            "frozen_selector_result": str(FROZEN_OUTPUT.relative_to(ROOT)),
            "frozen_selector_output_hashes": {item["id"]: item["output_hash"] for item in frozen["outputs"]},
        },
        "contract": {"hcx_calls": 0, "selector_enum_prompt_changed": False, "candidate_agent_changed": False, "retrieval_used": False},
        "scope_metrics": {
            "resolved_reference_accuracy": {"correct": resolved_correct, "total": resolved_total, "accuracy": round(resolved_correct / resolved_total, 4)},
            "unresolved_reference_safety": {"correct": unresolved_correct, "total": unresolved_total, "accuracy": round(unresolved_correct / unresolved_total, 4)},
            "subject_requirement_binding_error_count": binding_errors,
            "ambiguous_reference_unsafe_resolution_count": unsafe_ambiguous,
        },
        "details": details,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hcx_calls": 0, **payload["scope_metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
