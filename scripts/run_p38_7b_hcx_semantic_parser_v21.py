"""Run P38-7B isolated HCX-007 semantic parser v2.1 on P38-2 dev only."""
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
from src.experiments.hcx_semantic_planner_v21 import HCXSemanticPlannerV21
from src.experiments.semantic_contract_v21 import SemanticPlanV21
from src.experiments.semantic_contract_v21_evaluator import evaluate_v21_predictions
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


GOLD = ROOT / "question_bank/development/semantic_contract_v2_manual_gold.jsonl"
METADATA = ROOT / "question_bank/development/semantic_contract_v2_manual_gold_metadata.json"
V2_BASELINE = ROOT / "evaluation/p38_6_v2_ab_p38_2_subset.json"
OUTPUT = ROOT / "evaluation/p38_7b_v21_ab_p38_2_subset.json"
PACING_SECONDS = 6.0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _manifest_sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P38-7B requires configured HCX-007 Native Structured Outputs.")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P38-7B requires HCX_API_KEY and HCX_BASE_URL.")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def _track_essential_cases(score: dict) -> dict:
    expected = {
        "before_retirement": ("P38-2-002", "essential_qualifiers", "before_retirement"),
        "combined_limit": ("P38-2-004", "essential_qualifiers", "combined_limit"),
        "not_tax_exempt": ("P38-2-005", "essential_qualifiers", "not_tax_exempt"),
        "isa_maturity": ("P38-2-008", "essential_qualifiers", "isa_maturity"),
        "additional_credit": ("P38-2-008", "essential_qualifiers", "additional_credit"),
        "in_kind": ("P38-2-009", "essential_qualifiers", "in_kind"),
        "current": ("P38-2-011", "essential_qualifiers", "current"),
        "change_possibility": ("P38-2-011", "essential_qualifiers", "change_possibility"),
        "historical": ("P38-2-015", "essential_qualifiers", "historical"),
        "tax_timing_on_transfer": ("P38-2-017", "essential_qualifiers", "tax_timing_on_transfer"),
        "partial_vs_closure_tax": ("P38-2-018", "fields", "partial_withdrawal_tax"),
    }
    detail = {item["source_question_id"]: item for item in score["details"]}
    return {name: {"source_question_id": qid, "recovered": atom in detail[qid]["predicted"][component]} for name, (qid, component, atom) in expected.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because this command makes 18 live HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P38-7B makes live HCX calls; pass --execute after reviewing the frozen v2.1 contract.")

    all_rows = _rows(GOLD)
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if _manifest_sha(all_rows) != metadata["manifest_sha256"]:
        raise RuntimeError("Frozen P38-5 v2 manifest hash mismatch.")
    selected = [row for row in all_rows if row["source_split"] == "p38_2_development_after_execution"]
    if len(selected) != 18:
        raise RuntimeError(f"P38-7B requires exactly 18 P38-2 development rows, found {len(selected)}")

    settings = _settings()
    planner = HCXSemanticPlannerV21(config=settings, rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds))
    outputs, predictions, provider_errors = [], {}, 0
    for row in selected:
        qid = row["source_question_id"]
        try:
            result = planner.plan(row["question"])
            predictions[qid] = result.plan
            outputs.append({
                "source_question_id": qid, "schema_valid": result.schema_valid, "ontology_valid": result.ontology_valid,
                "unknown_atoms": list(result.unknown_atoms),
                "plan": {"subjects": list(result.plan.subjects), "fields": list(result.plan.fields), "essential_qualifiers": list(result.plan.qualifiers), "directional_transfers": [item.__dict__ for item in result.plan.transfers]},
                "diagnostic": result.diagnostic,
            })
        except GenerationError as error:
            provider_errors += 1
            predictions[qid] = SemanticPlanV21((), (), (), ())
            outputs.append({"source_question_id": qid, "schema_valid": False, "ontology_valid": False, "unknown_atoms": [], "plan": {"subjects": [], "fields": [], "essential_qualifiers": [], "directional_transfers": []}, "provider_error": str(error), "diagnostic": error.diagnostic})

    score_path = ROOT / "evaluation/.p38_7b_score_input.jsonl"
    score_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
    try:
        score = evaluate_v21_predictions(score_path, predictions)
    finally:
        score_path.unlink(missing_ok=True)
    baseline = json.loads(V2_BASELINE.read_text(encoding="utf-8"))
    runtime = {
        "schema_valid": {"valid": sum(item["schema_valid"] for item in outputs), "total": len(outputs)},
        "ontology_valid": {"valid": sum(item["ontology_valid"] for item in outputs), "total": len(outputs)},
        "unknown_ontology_values": sum(len(item["unknown_atoms"]) for item in outputs),
        "provider_errors": provider_errors,
        "live_hcx_calls": len(outputs),
    }
    result = {
        "experiment": "P38-7B Isolated HCX Structured Semantic Parser v2.1 A/B",
        "scope": "P38-2 18 development questions only",
        "candidate_agent_changed": False, "retrieval_used": False, "answer_generation_used": False,
        "citation_used": False, "policy_used": False,
        "input": {"manifest": str(GOLD.relative_to(ROOT)), "manifest_sha256": metadata["manifest_sha256"], "question_count": len(selected)},
        "contract": {"model": settings.hcx_model, "native_structured_outputs": True, "thinking_effort": "none", "min_request_start_interval_seconds": PACING_SECONDS, "generic_comparison_model_output": False, "directional_transfer_model_output": True, "precision_first": True},
        "runtime": runtime,
        "metrics": score,
        "essential_condition_tracker": _track_essential_cases(score),
        "frozen_v2_baseline": {"artifact": str(V2_BASELINE.relative_to(ROOT)), "runtime": baseline["runtime"], "metrics": baseline["metrics"]},
        "planner_outputs": outputs,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runtime": runtime, "component_f1": {name: value["f1"] for name, value in score["component_metrics"].items()}, "semantic_requirement_coverage": score["semantic_requirement_coverage"], "requirement_exact": score["requirement_exact"], "real_semantic_miss_count": score["real_semantic_miss_count"], "unsupported_extra_atom_count": score["unsupported_extra_atom_count"], "essential_condition_tracker": result["essential_condition_tracker"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
