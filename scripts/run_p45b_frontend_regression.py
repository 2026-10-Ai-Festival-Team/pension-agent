"""Recheck only P45's two repaired front-end failures with live selector.

P45 is now a development regression set.  This script deliberately does not
call answer generation and does not touch the six frozen generation failures.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
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
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


MANIFEST = ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl"
OUTPUT = ROOT / "evaluation/p45b_frontend_regression.json"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
PACING_SECONDS = 6.0
TARGETS = {"P45-003", "P45-004"}


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P45-B requires HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P45-B requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because this runs two live selector calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P45-B uses live selector calls; pass --execute")
    rows = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if row["id"] in TARGETS]
    if {row["id"] for row in rows} != TARGETS:
        raise RuntimeError("P45-B targets are missing from the frozen manifest")
    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    selector = ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter))
    preparation = ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX))
    outputs = []
    for row in rows:
        selected = selector.select(row["question"])
        selection = selected.selection
        frontend = {
            "status": selected.status,
            "active_subject": selected.active_subject,
            "allowed_requirements": list(selected.allowed_requirements),
            "selected_requirements": list(selection.selected_requirements) if selection else [],
        }
        plan = preparation.prepare(row["question"], frontend)
        expected = set(row["selected_requirements"])
        returned = set(frontend["selected_requirements"])
        gold_covered = {
            requirement: bool(set(row["gold_evidence"][requirement]) & set(plan.requirement_candidates.get(requirement, ())))
            for requirement in expected
        }
        outputs.append({
            "id": row["id"],
            "active_subject": selected.active_subject,
            "expected_active_subject": row["expected_active_subject"],
            "selected_requirements": frontend["selected_requirements"],
            "expected_requirements": row["selected_requirements"],
            "selector_status": selected.status,
            "schema_valid": selection.schema_valid if selection else False,
            "ontology_valid": selection.ontology_valid if selection else False,
            "unknown_requirements": list(selection.unknown_requirements) if selection else [],
            "preparation_status": plan.status,
            "requirement_candidate_ids": {key: list(value) for key, value in plan.requirement_candidates.items()},
            "scope_correct": selected.active_subject == row["expected_active_subject"],
            "requirement_exact": returned == expected,
            "gold_evidence_covered": gold_covered,
        })
    summary = {
        "target_count": len(outputs),
        "scope_correct": sum(item["scope_correct"] for item in outputs),
        "requirement_exact": sum(item["requirement_exact"] for item in outputs),
        "gold_evidence_covered": sum(all(item["gold_evidence_covered"].values()) for item in outputs),
        "schema_valid": sum(item["schema_valid"] for item in outputs),
        "ontology_valid": sum(item["ontology_valid"] for item in outputs),
        "unknown_requirement_count": sum(len(item["unknown_requirements"]) for item in outputs),
        "answer_generation_hcx_calls": 0,
        "candidate_or_browser_changed": False,
    }
    OUTPUT.write_text(json.dumps({"experiment": "P45-B Front-end Regression", "summary": summary, "outputs": outputs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
