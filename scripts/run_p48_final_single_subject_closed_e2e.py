"""Execute the frozen P48 fresh holdout through the checked E2E preparation contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _output_row, _settings, _summary
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever

HOLDOUT = ROOT / "question_bank/holdouts/p48_final_single_subject_closed_e2e.jsonl"
METADATA = ROOT / "question_bank/holdouts/p48_final_single_subject_closed_e2e_metadata.json"
OUTPUT = ROOT / "evaluation/p48_final_single_subject_closed_e2e.json"
CHECKPOINT = ROOT / "evaluation/.p48_final_single_subject_closed_e2e_checkpoint.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required: P48 makes live selector and answer calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P48 is a frozen fresh holdout; pass --execute only after reviewing its manifest")
    rows, metadata = _rows(), json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("P48 manifest is not frozen and validated")
    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    agent = DirectRequirementE2EAgent(
        scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
        preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
        generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
    )
    CHECKPOINT.unlink(missing_ok=True)
    outputs = []
    for row in rows:
        started = time.perf_counter()
        response = agent.answer(row["question"])
        output = _output_row(row, response, (time.perf_counter() - started) * 1000)
        outputs.append(output)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    payload = {
        "experiment": "P48 Final Fresh Single-Subject Closed E2E", "manifest": str(HOLDOUT.relative_to(ROOT)),
        "manifest_sha256": metadata["manifest_sha256"], "capability_boundary": metadata["excluded_capability"],
        "runtime": {"hcx_model": settings.hcx_model, "selector_and_answer_share_global_pacing_seconds": PACING_SECONDS, "candidate_or_browser_changed": False},
        "operational_summary": _summary(outputs), "outputs": outputs,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["operational_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
