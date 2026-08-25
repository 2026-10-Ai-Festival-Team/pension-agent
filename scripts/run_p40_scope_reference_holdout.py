"""Execute frozen P40 selector + resolver/binder holdout with checkpoints."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.direct_requirement_selector_evaluator import score_requirement_predictions
from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter

HOLDOUT = ROOT / "question_bank/holdouts/p40_scope_reference_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p40_scope_reference_holdout_metadata.json"
OUTPUT = ROOT / "evaluation/p40_scope_reference_holdout.json"
CHECKPOINT = ROOT / "evaluation/.p40_scope_reference_checkpoint.jsonl"
PACING_SECONDS = 6.0


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P40 requires configured HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P40 requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because P40 makes 18 live HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P40 is a fresh live holdout; pass --execute after reviewing its frozen manifest.")
    rows, metadata = _rows(), json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("P40 manifest is not frozen and validated")
    settings = _settings()
    selector = HCXDirectRequirementSelector(config=settings, rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds))
    resolver, binder = ScopeReferenceResolver(), DeterministicBinder()
    predictions: dict[str, tuple[str, ...]] = {}
    outputs, provider_errors = [], 0
    CHECKPOINT.unlink(missing_ok=True)
    for row in rows:
        try:
            selected = selector.select(row["question"])
            predictions[row["id"]] = selected.selected_requirements
            resolution = resolver.resolve(row["question"])
            binding = binder.bind(row["question"], resolution, selected.selected_requirements)
            stable = {"selected_requirements": list(selected.selected_requirements), "unresolved": selected.unresolved, "resolution": resolution.as_dict(), "binding": binding.as_dict()}
            output = {"id": row["id"], "schema_valid": selected.schema_valid, "ontology_valid": selected.ontology_valid, **stable, "output_hash": hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(), "unknown_requirements": list(selected.unknown_requirements), "diagnostic": selected.diagnostic}
        except GenerationError as error:
            provider_errors += 1
            predictions[row["id"]] = ()
            output = {"id": row["id"], "schema_valid": False, "ontology_valid": False, "selected_requirements": [], "unresolved": True, "resolution": None, "binding": None, "output_hash": None, "unknown_requirements": [], "provider_error": str(error), "diagnostic": error.diagnostic}
        outputs.append(output)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    runtime = {"schema_valid": {"valid": sum(item["schema_valid"] for item in outputs), "total": len(outputs)}, "ontology_valid": {"valid": sum(item["ontology_valid"] for item in outputs), "total": len(outputs)}, "unknown_requirement_count": sum(len(item["unknown_requirements"]) for item in outputs), "provider_errors": provider_errors, "live_hcx_calls": len(outputs)}
    scope_details, resolved_total = [], 0
    resolved_correct = unresolved_total = unresolved_correct = binding_errors = unsafe_ambiguous = 0
    for row, output in zip(rows, outputs):
        if output["resolution"] is None:
            scope_details.append({"id": row["id"], "status": "provider_error"})
            continue
        resolution, binding = output["resolution"], output["binding"]
        expected_behavior = row["expected_reference_behavior"]
        if expected_behavior == "resolved":
            resolved_total += 1
            correct = resolution["active_subjects"] == row["expected_active_subjects"] and not resolution["unresolved_references"]
            resolved_correct += int(correct)
            binding_error = bool(binding["scope_conflicts"] or binding["unresolved_references"] or any(item["status"] not in {"bound", "bound_comparison"} for item in binding["bindings"]))
            binding_errors += int(binding_error)
        else:
            unresolved_total += 1
            correct = bool(resolution["unresolved_references"]) and all(item["status"] == "unresolved_reference" for item in binding["bindings"])
            unresolved_correct += int(correct)
            unsafe_ambiguous += int(not correct)
            binding_error = not correct
        scope_details.append({"id": row["id"], "expected_reference_behavior": expected_behavior, "expected_active_subjects": row["expected_active_subjects"], "active_subjects": resolution["active_subjects"], "unresolved_references": resolution["unresolved_references"], "binding": binding, "reference_correct": correct, "binding_error": binding_error})
    metrics = score_requirement_predictions(rows, predictions, runtime)
    result = {"experiment": "P40 Fresh Scope/Reference Holdout", "input": {"manifest": str(HOLDOUT.relative_to(ROOT)), "manifest_sha256": _sha(rows), "question_count": len(rows)}, "contract": {"model": settings.hcx_model, "native_structured_outputs": True, "thinking_effort": "none", "min_request_start_interval_seconds": PACING_SECONDS, "selector_enum_prompt_changed": False, "candidate_agent_changed": False, "retrieval_used": False}, "runtime": runtime, "requirement_metrics": metrics, "scope_metrics": {"resolved_reference_accuracy": {"correct": resolved_correct, "total": resolved_total, "accuracy": round(resolved_correct / resolved_total, 4) if resolved_total else 1.0}, "unresolved_reference_safety": {"correct": unresolved_correct, "total": unresolved_total, "accuracy": round(unresolved_correct / unresolved_total, 4) if unresolved_total else 1.0}, "subject_requirement_binding_error_count": binding_errors, "ambiguous_reference_unsafe_resolution_count": unsafe_ambiguous, "details": scope_details}, "outputs": outputs}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CHECKPOINT.unlink(missing_ok=True)
    print(json.dumps({"runtime": runtime, "requirement_metrics": {key: value for key, value in metrics.items() if key not in {"details", "runtime"}}, "scope_metrics": {key: value for key, value in result["scope_metrics"].items() if key != "details"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
