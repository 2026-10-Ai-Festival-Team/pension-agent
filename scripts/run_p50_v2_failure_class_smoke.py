"""Run one exposed P50-v2 record per repaired runtime failure class."""
from __future__ import annotations

import json
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_fresh_p50_v2_final_holdout import _evaluate
from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever

HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v2.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
IDS = ("P50V2-016", "P50V2-023", "P50V2-043", "P50V2-044")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", type=int, default=1)
    args = parser.parse_args()
    if args.revision < 1:
        parser.error("revision must be positive")
    output = ROOT / f"evaluation/fresh_p50_v2_failure_class_smoke_v{args.revision}.json"
    if output.exists():
        raise RuntimeError("failure-class smoke already exists; do not duplicate HCX calls")
    rows = {row["id"]: row for row in (json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip())}
    if set(IDS) - set(rows):
        raise RuntimeError("immutable v2 smoke records are missing")
    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    agent = DirectRequirementE2EAgent(
        scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
        preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
        generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
    )
    outputs = []
    for record_id in IDS:
        row = rows[record_id]
        started = time.perf_counter()
        outputs.append(_evaluate(row, agent.answer(row["question"]), (time.perf_counter() - started) * 1000))
    failures = {item["id"]: item["failure_classes"] for item in outputs if item["failure_classes"]}
    payload = {
        "experiment": "P50 v2 repaired runtime failure-class smoke", "source_holdout": str(HOLDOUT.relative_to(ROOT)),
        "record_ids": list(IDS), "generator_model": settings.hcx_model, "outputs": outputs,
        "decision": "PASS" if not failures else "FAIL", "failures": failures,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": payload["decision"], "failures": failures}, ensure_ascii=False))


if __name__ == "__main__":
    main()
