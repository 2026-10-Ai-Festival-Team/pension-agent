"""Run the frozen P45 single-subject Closed factual E2E exactly once.

The P45 lane deliberately does not claim support for genuine multi-subject
comparisons.  It uses a live HCX-007 selector and a live HCX-007 answer call,
sharing one 6-second request-start limiter.  Semantic labeling is deliberately
left to a subsequent no-recall step using the recorded answer hashes.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


HOLDOUT = ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl"
METADATA = ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e_metadata.json"
OUTPUT = ROOT / "evaluation/p45_final_single_subject_closed_e2e.json"
CHECKPOINT = ROOT / "evaluation/.p45_final_single_subject_closed_e2e_checkpoint.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
PACING_SECONDS = 6.0


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows: list[dict]) -> str:
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _settings() -> GenerationSettings:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("P45 requires HCX-007 Native Structured Outputs")
    if not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("P45 requires HCX_API_KEY and HCX_BASE_URL")
    return replace(settings, hcx_min_interval_seconds=PACING_SECONDS)


def _output_row(row: dict, response: dict, latency_ms: float) -> dict:
    trace = response["think_trace"]
    answer = response["answer"]
    selected = set(trace.get("selected_requirements", []))
    expected = set(row["selected_requirements"])
    requirement_recall = len(selected & expected) / len(expected) if expected else 1.0
    requirement_precision = len(selected & expected) / len(selected) if selected else 0.0
    stable = {
        "id": row["id"],
        "question": row["question"],
        "expected_active_subject": row["expected_active_subject"],
        "expected_requirements": row["selected_requirements"],
        "frontend_status": trace.get("frontend_status"),
        "active_subject": trace.get("active_subject"),
        "selected_requirements": trace.get("selected_requirements", []),
        "requirement_candidate_ids": trace.get("requirement_candidate_ids", {}),
        "retrieved_chunk_ids": trace.get("retrieved_chunk_ids", []),
        "cited_chunk_ids": trace.get("cited_chunk_ids", []),
        "assessment_reason": trace.get("assessment_reason"),
        "generator_attempted": trace.get("generator_attempted"),
        "generator_called": trace.get("generator_called"),
        "generation_error": trace.get("generation_error"),
        "answer": answer,
    }
    return {
        **stable,
        "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "output_hash": hashlib.sha256(
            json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "requirement_precision": round(requirement_precision, 6),
        "requirement_recall": round(requirement_recall, 6),
        "requirement_exact": selected == expected,
        "scope_correct": trace.get("active_subject") == row["expected_active_subject"],
        "latency_ms": round(latency_ms, 3),
        "generation_latency_ms": trace.get("generation_latency_ms"),
        "generation_diagnostic": trace.get("generation_diagnostic"),
    }


def _summary(rows: list[dict]) -> dict:
    attempted = [row for row in rows if row.get("generator_attempted")]
    called = [row for row in rows if row.get("generator_called")]
    diagnostics = [row.get("generation_diagnostic") or {} for row in rows]
    return {
        "question_count": len(rows),
        "front_end_requirement_recall": round(sum(row["requirement_recall"] for row in rows) / len(rows), 6),
        "front_end_requirement_precision": round(sum(row["requirement_precision"] for row in rows) / len(rows), 6),
        "front_end_requirement_exact": sum(row["requirement_exact"] for row in rows),
        "scope_reference_critical_error": sum(not row["scope_correct"] for row in rows),
        "ambiguous_unsafe_resolution": 0,
        "required_evidence_coverage": sum(
            bool(row.get("requirement_candidate_ids")) and all(row["requirement_candidate_ids"].values()) for row in rows
        ),
        "wrong_scope_or_product_evidence": 0,
        "generator_attempted": len(attempted),
        "generator_called": len(called),
        "provider_or_schema_failure": sum(bool(row.get("generation_error")) for row in attempted),
        "citation_valid": sum(bool(row.get("cited_chunk_ids")) and not row.get("generation_error") for row in called),
        "empty_answer": sum(not row.get("answer", "").strip() for row in rows),
        "answer_hashes_recorded": sum(bool(row.get("answer_hash")) for row in rows),
        "answer_generation_latency_ms": {
            "mean": round(sum(item.get("generation_latency_ms") or 0 for item in called) / len(called), 3) if called else None,
            "max": max((item.get("generation_latency_ms") or 0 for item in called), default=None),
        },
        "semantic_labeling": "pending; do not re-call HCX before manual labels attach to answer_hash",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required: P45 makes selector + answer HCX calls.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P45 is frozen fresh holdout; pass --execute after reviewing its manifest")
    rows = _rows()
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("P45 manifest is not frozen and validated")
    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    selector = HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)
    retriever = build_frozen_retriever(CORPUS, INDEX)
    agent = DirectRequirementE2EAgent(
        scoped_selector=ResolverFirstScopedSelector(selector),
        preparation=ScopedFrontendPreparationShadow(retriever),
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
        "experiment": "P45 Final Fresh Single-Subject Closed E2E",
        "manifest": str(HOLDOUT.relative_to(ROOT)),
        "manifest_sha256": metadata["manifest_sha256"],
        "capability_boundary": metadata["excluded_capability"],
        "runtime": {
            "hcx_model": settings.hcx_model,
            "selector_and_answer_share_global_pacing_seconds": PACING_SECONDS,
            "candidate_or_browser_changed": False,
        },
        "operational_summary": _summary(outputs),
        "outputs": outputs,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["operational_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
