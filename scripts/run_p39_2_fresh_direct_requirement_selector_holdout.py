"""Execute frozen P39-2 direct-selector holdout with HCX only after review."""
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
from src.experiments.direct_requirement_selector_evaluator import score_requirement_predictions, score_scope_errors
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


HOLDOUT = ROOT / "question_bank/holdouts/p39_2_direct_requirement_selector_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p39_2_direct_requirement_selector_holdout_metadata.json"
OUTPUT = ROOT / "evaluation/p39_2_fresh_direct_requirement_selector_holdout.json"
CHECKPOINT = ROOT / "evaluation/.p39_2_direct_requirement_selector_checkpoint.jsonl"
PACING_SECONDS = 6.0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest_sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("fresh direct-selector execution requires configured HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("fresh direct-selector execution requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because a fresh holdout makes live HCX calls.")
    parser.add_argument("--manifest", type=Path, default=HOLDOUT)
    parser.add_argument("--metadata", type=Path, default=METADATA)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--experiment", default="P39-2 Fresh Direct-Selector Holdout")
    args = parser.parse_args()
    if not args.execute:
        parser.error("fresh holdout execution requires --execute after reviewing its frozen manifest.")
    manifest, metadata_path, output_path, checkpoint = args.manifest.resolve(), args.metadata.resolve(), args.output.resolve(), args.checkpoint.resolve()
    rows = _rows(manifest)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    manifest_sha = _manifest_sha(rows)
    if metadata.get("manifest_sha256") != manifest_sha or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("manifest is not the frozen, validated manifest")

    settings = _settings()
    selector = HCXDirectRequirementSelector(
        config=settings,
        rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    predictions: dict[str, tuple[str, ...]] = {}
    product_codes: dict[str, tuple[str, ...]] = {}
    outputs, provider_errors = [], 0
    # Persist each response before proceeding.  An evaluator defect must never
    # destroy a completed fresh-holdout run or tempt a caller to re-query it.
    checkpoint.unlink(missing_ok=True)
    for row in rows:
        try:
            result = selector.select(row["question"])
            predictions[row["id"]] = result.selected_requirements
            product_codes[row["id"]] = result.resolved_product_codes
            stable_output = {"selected_requirements": list(result.selected_requirements), "resolved_product_codes": list(result.resolved_product_codes), "unresolved": result.unresolved}
            output = {
                "id": row["id"], "schema_valid": result.schema_valid, "ontology_valid": result.ontology_valid,
                **stable_output, "output_hash": hashlib.sha256(json.dumps(stable_output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                "unknown_requirements": list(result.unknown_requirements), "diagnostic": result.diagnostic,
            }
            outputs.append(output)
        except GenerationError as error:
            provider_errors += 1
            predictions[row["id"]], product_codes[row["id"]] = (), ()
            output = {"id": row["id"], "schema_valid": False, "ontology_valid": False, "unresolved": True, "selected_requirements": [], "resolved_product_codes": [], "output_hash": None, "unknown_requirements": [], "provider_error": str(error), "diagnostic": error.diagnostic}
            outputs.append(output)
        with checkpoint.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    runtime = {
        "schema_valid": {"valid": sum(item["schema_valid"] for item in outputs), "total": len(outputs)},
        "ontology_valid": {"valid": sum(item["ontology_valid"] for item in outputs), "total": len(outputs)},
        "unknown_requirement_count": sum(len(item["unknown_requirements"]) for item in outputs),
        "provider_errors": provider_errors,
        "live_hcx_calls": len(outputs),
    }
    metrics = score_requirement_predictions(rows, predictions, runtime)
    result = {
        "experiment": args.experiment,
        "input": {"manifest": str(manifest.relative_to(ROOT)), "manifest_sha256": manifest_sha, "question_count": len(rows)},
        "contract": {"model": settings.hcx_model, "native_structured_outputs": True, "thinking_effort": "none", "min_request_start_interval_seconds": PACING_SECONDS, "candidate_agent_changed": False, "retrieval_used": False, "answer_generation_used": False, "citation_used": False, "policy_used": False},
        "runtime": runtime,
        "metrics": metrics,
        "scope_errors": score_scope_errors(rows, predictions, product_codes),
        "selector_outputs": outputs,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint.unlink(missing_ok=True)
    print(json.dumps({"runtime": runtime, "metrics": {key: value for key, value in metrics.items() if key not in {"details", "runtime"}}, "scope_errors": result["scope_errors"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
