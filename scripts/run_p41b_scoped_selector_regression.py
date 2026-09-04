"""Run the P41-B scoped-selector regression; only two HCX dev calls."""
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
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.generation.errors import GenerationError
from src.generation.rate_limit import GlobalMinIntervalLimiter


HOLDOUT = ROOT / "question_bank/holdouts/p41_scope_requirement_holdout.jsonl"
OUTPUT = ROOT / "evaluation/p41b_scoped_selector_regression.json"
CHECKPOINT = ROOT / "evaluation/.p41b_scoped_selector_checkpoint.jsonl"
TARGET_IDS = ("P41-008", "P41-010", "P41-011")
PACING_SECONDS = 6.0


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P41-B requires HCX-007 Native Structured Outputs")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because P41-B makes at most two live HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P41-B requires explicit --execute")
    rows = [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row["id"] in TARGET_IDS]
    if tuple(row["id"] for row in rows) != TARGET_IDS:
        raise RuntimeError("P41-B target rows are not stable")
    settings = _settings()
    base = HCXDirectRequirementSelector(
        config=settings,
        rate_limiter=GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    pipeline = ResolverFirstScopedSelector(base)
    CHECKPOINT.unlink(missing_ok=True)
    outputs, hcx_calls, errors = [], 0, 0
    for row in rows:
        try:
            result = pipeline.select(row["question"])
            selection = result.selection
            hcx_calls += int(selection is not None)
            stable = {
                "status": result.status,
                "active_subject": result.active_subject,
                "allowed_requirements": list(result.allowed_requirements),
                "selected_requirements": list(selection.selected_requirements) if selection else [],
                "unresolved": selection.unresolved if selection else True,
                "resolution": result.resolution.as_dict(),
                "binding": result.binding.as_dict() if result.binding else None,
                "reason": result.reason,
            }
            output = {"id": row["id"], **stable, "schema_valid": selection.schema_valid if selection else True, "ontology_valid": selection.ontology_valid if selection else True, "output_hash": hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()}
        except GenerationError as error:
            errors += 1
            output = {"id": row["id"], "status": "provider_error", "provider_error": str(error), "diagnostic": error.diagnostic, "output_hash": None}
        outputs.append(output)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    by_id = {item["id"]: item for item in outputs}
    checks = {
        "p41_008_unresolved_without_hcx": by_id["P41-008"]["status"] == "unresolved_scope",
        "p41_010_no_pension_savings_extra": "pension_savings.withdrawal.tax_treatment" not in by_id["P41-010"].get("selected_requirements", []),
        "p41_010_all_selected_in_filtered_catalog": set(by_id["P41-010"].get("selected_requirements", [])) <= set(by_id["P41-010"].get("allowed_requirements", [])),
        "p41_011_no_dc_operation_party_extra": "DC.operation_party" not in by_id["P41-011"].get("selected_requirements", []),
        "binder_adds_no_requirement": all(not item.get("binding") or {entry["requirement"] for entry in item["binding"]["bindings"]} <= set(item.get("selected_requirements", [])) for item in outputs),
        "provider_errors": errors,
        "live_hcx_calls": hcx_calls,
        "candidate_agent_changed": False,
    }
    payload = {
        "experiment": "P41-B Resolver-First Scoped Selector Regression",
        "input": {"holdout": str(HOLDOUT.relative_to(ROOT)), "target_ids": list(TARGET_IDS)},
        "contract": {
            "full_catalog_enum_changed": False,
            "precision_instruction_added": True,
            "subject_filtered_schema_experiment": True,
            "candidate_agent_changed": False,
            "retrieval_used": False,
            "hcx_calls": hcx_calls,
        },
        "outputs": outputs,
        "checks": checks,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CHECKPOINT.unlink(missing_ok=True)
    print(json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
