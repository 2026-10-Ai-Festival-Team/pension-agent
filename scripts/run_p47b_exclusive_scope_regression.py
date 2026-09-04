"""Recheck exclusive-scope connector behavior without answer generation.

P45/P47 are development regressions.  This script calls the scoped selector
only and verifies that the direct gold evidence remains preparable.
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
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector, requirements_for_active_subject
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


MANIFESTS = (
    (ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl", "P45-004"),
    (ROOT / "question_bank/holdouts/p47_final_single_subject_closed_e2e.jsonl", "P47-004"),
)
OUTPUT = ROOT / "evaluation/p47b_exclusive_scope_regression.json"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
PACING_SECONDS = 6.0


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P47-B requires HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P47-B requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required because P47-B makes two live selector calls.")
    parser.add_argument("--reuse", action="store_true", help="Reuse the frozen live selector output; recompute preparation only.")
    args = parser.parse_args()
    if args.execute == args.reuse:
        parser.error("pass exactly one of --execute or --reuse")
    rows = []
    for manifest, target in MANIFESTS:
        found = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line)["id"] == target]
        if len(found) != 1:
            raise RuntimeError(f"missing exclusive-scope target {target}")
        rows.extend(found)
    prior = {}
    if args.reuse:
        if not OUTPUT.exists():
            raise RuntimeError("--reuse requires an existing P47-B selector output")
        prior = {item["id"]: item for item in json.loads(OUTPUT.read_text(encoding="utf-8"))["outputs"]}
        if set(prior) != {row["id"] for row in rows}:
            raise RuntimeError("P47-B prior selector output does not match the frozen targets")
    else:
        settings = _settings()
        limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
        selector = ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter))
    preparation = ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX))
    outputs = []
    for row in rows:
        if args.reuse:
            old = prior[row["id"]]
            active, selected = old["active_subject"], old["selected_requirements"]
            status = "selected" if active else "unresolved_scope"
            schema_valid, ontology_valid = old["schema_valid"], old["ontology_valid"]
            unknown = old["unknown_requirements"]
        else:
            scoped = selector.select(row["question"])
            selection = scoped.selection
            active, selected = scoped.active_subject, list(selection.selected_requirements) if selection else []
            status = scoped.status
            schema_valid = selection.schema_valid if selection else False
            ontology_valid = selection.ontology_valid if selection else False
            unknown = list(selection.unknown_requirements) if selection else []
        allowed = list(requirements_for_active_subject(active)) if active else []
        plan = preparation.prepare(row["question"], {
            "status": status, "active_subject": active, "allowed_requirements": allowed, "selected_requirements": selected,
        })
        expected = set(row["selected_requirements"])
        outputs.append({
            "id": row["id"], "active_subject": active, "expected_active_subject": row["expected_active_subject"],
            "selected_requirements": selected, "expected_requirements": row["selected_requirements"],
            "allowed_requirements": allowed,
            "scope_correct": active == row["expected_active_subject"],
            "requirement_exact": set(selected) == expected,
            "gold_evidence_covered": {
                requirement: bool(set(row["gold_evidence"][requirement]) & set(plan.requirement_candidates.get(requirement, ())))
                for requirement in expected
            },
            "schema_valid": schema_valid, "ontology_valid": ontology_valid, "unknown_requirements": unknown,
        })
    summary = {
        "target_count": len(outputs), "scope_correct": sum(item["scope_correct"] for item in outputs),
        "requirement_exact": sum(item["requirement_exact"] for item in outputs),
        "gold_evidence_covered": sum(all(item["gold_evidence_covered"].values()) for item in outputs),
        "schema_valid": sum(item["schema_valid"] for item in outputs), "ontology_valid": sum(item["ontology_valid"] for item in outputs),
        "unknown_requirement_count": sum(len(item["unknown_requirements"]) for item in outputs),
        "answer_generation_hcx_calls": 0, "candidate_or_browser_changed": False,
    }
    OUTPUT.write_text(json.dumps({"experiment": "P47-B Exclusive Scope Regression", "selector_output_reused": args.reuse, "summary": summary, "outputs": outputs}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
