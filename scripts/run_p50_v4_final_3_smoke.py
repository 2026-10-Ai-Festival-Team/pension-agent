"""Actual HCX-007 smoke for the three final Fresh P50 v4 blocker classes."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_fresh_p50_v2_final_holdout import _evaluate
from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.generation.versioned_generator_prompt import load_generator_prompt
from src.orchestration.retrieval_service import build_frozen_retriever

HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v4.jsonl"
OUTPUT = ROOT / "evaluation/p50_v4_final_3_smoke_v1.json"
CHECKPOINT = ROOT / "evaluation/.p50_v4_final_3_smoke_checkpoint_v1.jsonl"
IDS = ("P50V4-020", "P50V4-031", "P50V4-033")
PROMPT_SHA256 = "05763afaa082af98832a04d29001a9d2ee1f353308cd4cc8e651e3b15b9c83a8"


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("smoke artifact already exists; duplicate HCX calls are prohibited")
    rows_by_id = {json.loads(line)["id"]: json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()}
    rows = [rows_by_id[row_id] for row_id in IDS]
    done = {}
    if CHECKPOINT.exists():
        done = {json.loads(line)["id"]: json.loads(line) for line in CHECKPOINT.read_text(encoding="utf-8").splitlines() if line.strip()}

    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    agent = DirectRequirementE2EAgent(
        ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
        ScopedFrontendPreparationShadow(build_frozen_retriever(ROOT / "data/parsed/chunks.jsonl", ROOT / "data/indexes/bm25/simple")),
        HyperClovaXGenerator(config=settings, rate_limiter=limiter),
        prompt_contract=load_generator_prompt("generator_prompt_final_v2_1"),
    )
    for row in rows:
        if row["id"] in done:
            continue
        started = time.perf_counter()
        done[row["id"]] = _evaluate(row, agent.answer(row["question"]), (time.perf_counter() - started) * 1000)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(done[row["id"]], ensure_ascii=False) + "\n")

    outputs = [done[row_id] for row_id in IDS]
    failure_classes = sorted({failure for output in outputs for failure in output["failure_classes"]})
    summary = {
        "record_count": len(outputs),
        "pass_count": sum(output["strict_pass"] for output in outputs),
        "failure_classes": failure_classes,
        "decision": "GO" if not failure_classes else "NO_GO",
    }
    artifact = {
        "experiment": "P50 v4 final three-blocker targeted HCX-007 smoke",
        "prompt_sha256": PROMPT_SHA256,
        "outputs": outputs,
        "summary": summary,
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
