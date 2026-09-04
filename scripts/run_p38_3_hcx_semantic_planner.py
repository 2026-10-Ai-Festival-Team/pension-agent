"""Run P38-3: an isolated HCX-007 Structured Output semantic parser.

This experiment sends only a lexical-normalized question to HCX.  It never
imports the candidate Agent or supplies retrieval context, citations, or
answer-generation instructions.
"""
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
from src.experiments.compositional_canonicalizer import SemanticAtoms
from src.experiments.compositional_evaluator import evaluate_predictions
from src.experiments.hcx_semantic_planner import HCXSemanticPlanner
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


DEFAULT_QUESTIONS = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout.jsonl"
DEFAULT_METADATA = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout_metadata.json"
DEFAULT_OUTPUT = ROOT / "evaluation/p38_3_hcx_semantic_planner_results.json"
PACING_SECONDS = 6.0


def _manifest_sha256(path: Path) -> str:
    # Holdout builders hash canonical JSON rows rather than JSONL bytes, so
    # harmless formatting/newline changes cannot masquerade as a new manifest.
    rows = _load_rows(path)
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _require_live_settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx":
        raise RuntimeError("P38-3 requires GENERATOR_BACKEND=hcx; no fake parser is permitted.")
    if settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P38-3 requires HCX_MODEL=HCX-007 for Native Structured Outputs.")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P38-3 requires HCX_API_KEY and HCX_BASE_URL.")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def _empty_atoms() -> SemanticAtoms:
    return SemanticAtoms((), (), (), ())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Authorize the isolated live HCX run.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.execute:
        parser.error("P38-3 makes live HCX calls. Re-run with --execute after reviewing the frozen inputs.")

    rows = _load_rows(args.questions)
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    manifest_sha256 = _manifest_sha256(args.questions)
    if manifest_sha256 != metadata.get("manifest_sha256"):
        raise RuntimeError("Question manifest hash does not match frozen P38-2 metadata.")

    settings = _require_live_settings()
    planner = HCXSemanticPlanner(
        config=settings,
        rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    predictions: dict[str, SemanticAtoms] = {}
    output_rows: list[dict] = []
    provider_errors = 0
    for row in rows:
        question_id = row["source_question_id"]
        try:
            response = planner.plan(row["question"])
            predictions[question_id] = response.atoms
            output_rows.append({
                "source_question_id": question_id,
                "schema_valid": response.schema_valid,
                "ontology_valid": response.ontology_valid,
                "unknown_atoms": list(response.unknown_atoms),
                "atoms": {
                    "subjects": list(response.atoms.subjects),
                    "actions": list(response.atoms.actions),
                    "fields": list(response.atoms.fields),
                    "modifiers": list(response.atoms.modifiers),
                },
                "diagnostic": response.diagnostic,
            })
        except GenerationError as error:
            provider_errors += 1
            predictions[question_id] = _empty_atoms()
            output_rows.append({
                "source_question_id": question_id,
                "schema_valid": False,
                "ontology_valid": False,
                "unknown_atoms": [],
                "atoms": {"subjects": [], "actions": [], "fields": [], "modifiers": []},
                "provider_error": str(error),
                "diagnostic": error.diagnostic,
            })

    score = evaluate_predictions(args.questions, predictions)
    schema_valid = sum(item["schema_valid"] for item in output_rows)
    ontology_valid = sum(item["ontology_valid"] for item in output_rows)
    unknown_atoms = sum(len(item["unknown_atoms"]) for item in output_rows)
    component_errors = {
        "missing_atoms": 0,
        "extra_atoms": 0,
    }
    for detail in score["details"]:
        for component in ("subjects", "actions", "fields", "modifiers"):
            predicted = set(detail["predicted"][component])
            gold = set(detail["gold"][component])
            component_errors["missing_atoms"] += len(gold - predicted)
            component_errors["extra_atoms"] += len(predicted - gold)

    result = {
        "experiment": "P38-3 isolated HCX-007 Structured Semantic Planner",
        "purpose": "Feasibility comparison on P38-2 dev data only; not a generalization claim.",
        "candidate_agent_changed": False,
        "retrieval_used": False,
        "answer_generation_used": False,
        "citation_used": False,
        "hcx_calls": len(rows),
        "input": {
            "questions": str(args.questions.relative_to(ROOT)),
            "manifest_sha256": manifest_sha256,
            "status": metadata.get("status"),
        },
        "hcx_contract": {
            "model": settings.hcx_model,
            "native_structured_outputs": True,
            "thinking_effort": "none",
            "min_request_start_interval_seconds": PACING_SECONDS,
            "ontology_constrained": True,
        },
        "planner_contract": {
            "lexical_normalization": "explicit entity aliases and product-code casing only",
            "ontology_validator": "fail closed on malformed or unknown atom values",
            "raw_response_persisted": False,
        },
        "runtime": {
            "schema_valid": {"valid": schema_valid, "total": len(rows), "rate": round(schema_valid / len(rows), 4)},
            "ontology_valid": {"valid": ontology_valid, "total": len(rows), "rate": round(ontology_valid / len(rows), 4)},
            "unknown_ontology_values": unknown_atoms,
            "provider_errors": provider_errors,
            **component_errors,
        },
        "metrics": score,
        "planner_outputs": output_rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "question_count": len(rows),
        "schema_valid": result["runtime"]["schema_valid"],
        "ontology_valid": result["runtime"]["ontology_valid"],
        "provider_errors": provider_errors,
        "component_f1": {name: metric["f1"] for name, metric in score["component_metrics"].items()},
        "multi_atom_field_recall": score["multi_atom_field_recall"],
        "requirement_exact": score["requirement_composition"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
