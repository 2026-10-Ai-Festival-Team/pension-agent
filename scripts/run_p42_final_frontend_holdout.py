"""Execute frozen P42 once using the resolver-first scoped selector path."""
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
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


HOLDOUT = ROOT / "question_bank/holdouts/p42_final_frontend_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p42_final_frontend_holdout_metadata.json"
OUTPUT = ROOT / "evaluation/p42_final_frontend_holdout.json"
CHECKPOINT = ROOT / "evaluation/.p42_final_frontend_checkpoint.jsonl"
PACING_SECONDS = 6.0


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P42 requires HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P42 requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def _effective_subjects(binding: dict | None) -> list[str]:
    if binding is None:
        return []
    bound = []
    for item in binding["bindings"]:
        if item["status"] == "bound" and item["subject"]:
            bound.extend(subject for subject in item["subject"].split("+") if subject not in bound)
    return bound or list(binding["active_subjects"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because P42 makes up to 14 live HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P42 is a fresh holdout; pass --execute after reviewing frozen manifest")
    rows, metadata = _rows(), json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("P42 manifest is not frozen and validated")
    settings = _settings()
    base = HCXDirectRequirementSelector(
        config=settings,
        rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    pipeline = ResolverFirstScopedSelector(base)
    predictions: dict[str, tuple[str, ...]] = {}
    outputs, hcx_calls, provider_errors = [], 0, 0
    CHECKPOINT.unlink(missing_ok=True)
    for row in rows:
        try:
            selected = pipeline.select(row["question"])
            selection = selected.selection
            hcx_calls += int(selection is not None)
            predictions[row["id"]] = selection.selected_requirements if selection else ()
            stable = {
                "status": selected.status,
                "active_subject": selected.active_subject,
                "allowed_requirements": list(selected.allowed_requirements),
                "selected_requirements": list(selection.selected_requirements) if selection else [],
                "unresolved": selection.unresolved if selection else True,
                "resolution": selected.resolution.as_dict(),
                "binding": selected.binding.as_dict() if selected.binding else None,
                "reason": selected.reason,
            }
            output = {
                "id": row["id"], **stable,
                "schema_valid": selection.schema_valid if selection else None,
                "ontology_valid": selection.ontology_valid if selection else None,
                "unknown_requirements": list(selection.unknown_requirements) if selection else [],
                "output_hash": hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
            }
        except GenerationError as error:
            provider_errors += 1
            predictions[row["id"]] = ()
            output = {"id": row["id"], "status": "provider_error", "provider_error": str(error), "diagnostic": error.diagnostic, "output_hash": None}
        outputs.append(output)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    runtime = {
        "live_hcx_calls": hcx_calls,
        "provider_errors": provider_errors,
        "schema_valid": {"valid": sum(item.get("schema_valid") is True for item in outputs), "total": hcx_calls},
        "ontology_valid": {"valid": sum(item.get("ontology_valid") is True for item in outputs), "total": hcx_calls},
        "unknown_requirement_count": sum(len(item.get("unknown_requirements", [])) for item in outputs),
    }
    selector_rows = [row for row in rows if row["selector_evaluable"]]
    requirement_metrics = score_requirement_predictions(selector_rows, predictions, runtime)
    scope_details = []
    resolved_total = resolved_correct = unresolved_total = unresolved_correct = binding_errors = unsafe = out_of_scope_extras = 0
    for row, output in zip(rows, outputs):
        behavior = row["expected_reference_behavior"]
        if output["status"] == "provider_error":
            scope_details.append({"id": row["id"], "status": "provider_error"})
            continue
        binding = output["binding"]
        if behavior == "unresolved":
            unresolved_total += 1
            correct = output["status"] == "unresolved_scope" and bool(output["resolution"]["unresolved_references"])
            unresolved_correct += int(correct)
            unsafe += int(not correct)
            binding_error = not correct
            effective = []
        else:
            resolved_total += 1
            effective = _effective_subjects(binding)
            binding_error = output["status"] != "selected" or bool(binding["scope_conflicts"] or binding["unresolved_references"])
            correct = effective == row["expected_active_subjects"] and not binding_error
            resolved_correct += int(correct)
            allowed = set(output["allowed_requirements"])
            out_of_scope_extras += sum(value not in allowed for value in output["selected_requirements"])
        binding_errors += int(binding_error)
        scope_details.append({
            "id": row["id"], "expected_reference_behavior": behavior,
            "expected_active_subjects": row["expected_active_subjects"],
            "status": output["status"], "effective_bound_subjects": effective,
            "selected_requirements": output["selected_requirements"],
            "allowed_requirements": output["allowed_requirements"],
            "resolution": output["resolution"], "binding": binding,
            "scope_correct": correct, "binding_error": binding_error,
        })
    payload = {
        "experiment": "P42 Final Fresh Front-End Holdout",
        "input": {"manifest": str(HOLDOUT.relative_to(ROOT)), "manifest_sha256": _sha(rows), "question_count": len(rows)},
        "contract": {
            "resolver_first": True, "subject_filtered_schema": True, "precision_instruction": True,
            "candidate_agent_changed": False, "retrieval_used": False,
            "native_structured_outputs": True, "thinking_effort": "none",
            "min_request_start_interval_seconds": PACING_SECONDS,
        },
        "runtime": runtime,
        "requirement_metrics": requirement_metrics,
        "scope_metrics": {
            "final_scope_resolution_accuracy": {"correct": resolved_correct, "total": resolved_total, "accuracy": round(resolved_correct / resolved_total, 4) if resolved_total else 1.0},
            "unresolved_reference_safety": {"correct": unresolved_correct, "total": unresolved_total, "accuracy": round(unresolved_correct / unresolved_total, 4) if unresolved_total else 1.0},
            "subject_requirement_binding_error_count": binding_errors,
            "ambiguous_reference_unsafe_resolution_count": unsafe,
            "out_of_scope_extra_requirement_count": out_of_scope_extras,
            "details": scope_details,
        },
        "outputs": outputs,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CHECKPOINT.unlink(missing_ok=True)
    print(json.dumps({
        "runtime": runtime,
        "requirement_metrics": {key: value for key, value in requirement_metrics.items() if key not in {"details", "runtime"}},
        "scope_metrics": {key: value for key, value in payload["scope_metrics"].items() if key != "details"},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
