"""Run P39-1 isolated A/B/C requirement-selection comparison on 18 dev rows."""
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
from src.experiments.direct_requirement_selector_evaluator import (
    frozen_v21_predictions,
    legacy_planner_requirements,
    score_requirement_predictions,
)
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


GOLD = ROOT / "question_bank/development/p39_1_direct_requirement_selector_gold.jsonl"
V21_BASELINE = ROOT / "evaluation/p38_7b_v21_ab_p38_2_subset.json"
OUTPUT = ROOT / "evaluation/p39_1_direct_requirement_selector_ab.json"
PACING_SECONDS = 6.0


def _rows() -> list[dict]:
    rows = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != 18:
        raise RuntimeError(f"P39-1 requires 18 manually frozen rows, found {len(rows)}")
    if any(row.get("annotation_source") != "manual" or row.get("auto_converted") for row in rows):
        raise RuntimeError("P39-1 gold must remain manual and non-auto-converted")
    return rows


def _manifest_sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P39-1 requires configured HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P39-1 requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because C makes 18 live HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P39-1 is a live isolated HCX experiment; pass --execute after reviewing the frozen gold.")

    rows = _rows()
    settings = _settings()
    baseline_a = {row["source_question_id"]: legacy_planner_requirements(row["question"]) for row in rows}
    baseline_b = frozen_v21_predictions(V21_BASELINE)

    selector = HCXDirectRequirementSelector(
        config=settings,
        rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    predictions_c: dict[str, tuple[str, ...]] = {}
    outputs, provider_errors = [], 0
    for row in rows:
        qid = row["source_question_id"]
        try:
            result = selector.select(row["question"])
            predictions_c[qid] = result.selected_requirements
            outputs.append({
                "source_question_id": qid,
                "schema_valid": result.schema_valid,
                "ontology_valid": result.ontology_valid,
                "unresolved": result.unresolved,
                "selected_requirements": list(result.selected_requirements),
                "resolved_product_codes": list(result.resolved_product_codes),
                "unknown_requirements": list(result.unknown_requirements),
                "diagnostic": result.diagnostic,
            })
        except GenerationError as error:
            provider_errors += 1
            predictions_c[qid] = ()
            outputs.append({
                "source_question_id": qid, "schema_valid": False, "ontology_valid": False,
                "unresolved": True, "selected_requirements": [], "resolved_product_codes": [],
                "unknown_requirements": [], "provider_error": str(error), "diagnostic": error.diagnostic,
            })

    runtime_c = {
        "schema_valid": {"valid": sum(item["schema_valid"] for item in outputs), "total": len(outputs)},
        "ontology_valid": {"valid": sum(item["ontology_valid"] for item in outputs), "total": len(outputs)},
        "unknown_requirement_count": sum(len(item["unknown_requirements"]) for item in outputs),
        "provider_errors": provider_errors,
        "live_hcx_calls": len(outputs),
    }
    product_resolution = {
        "exact": sum(tuple(item["resolved_product_codes"]) == tuple(row["expected_product_codes"]) for item, row in zip(outputs, rows)),
        "total": len(rows),
    }
    result = {
        "experiment": "P39-1 isolated direct canonical-requirement selector A/B/C",
        "scope": "P38-2 18 development questions only; no candidate integration",
        "candidate_agent_changed": False,
        "retrieval_used": False,
        "answer_generation_used": False,
        "citation_used": False,
        "policy_used": False,
        "input": {"manifest": str(GOLD.relative_to(ROOT)), "manifest_sha256": _manifest_sha(rows), "question_count": len(rows)},
        "contract": {"model": settings.hcx_model, "native_structured_outputs": True, "thinking_effort": "none", "min_request_start_interval_seconds": PACING_SECONDS, "direct_multi_label_enum": True, "product_identity_deterministic": True},
        "methods": {
            "A_existing_production_planner": score_requirement_predictions(rows, baseline_a, {"live_hcx_calls": 0, "provider_errors": 0}),
            "B_frozen_p38_v21_atom_parser": score_requirement_predictions(rows, baseline_b, {"artifact": str(V21_BASELINE.relative_to(ROOT)), "live_hcx_calls": 0, "provider_errors": 0}),
            "C_p39_direct_requirement_selector": score_requirement_predictions(rows, predictions_c, runtime_c),
        },
        "C_runtime": runtime_c,
        "C_product_identity_resolution": product_resolution,
        "C_selector_outputs": outputs,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compact = {name: {key: value for key, value in metrics.items() if key not in {"details", "runtime"}} for name, metrics in result["methods"].items()}
    print(json.dumps({"methods": compact, "C_runtime": runtime_c, "C_product_identity_resolution": product_resolution}, ensure_ascii=False))


if __name__ == "__main__":
    main()
