"""Run P22 smoke/full HCX evaluation with auditable global request timing."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.factory import build_answer_generator
from src.orchestration.retrieval_service import build_frozen_retriever


SMOKE_IDS = ("R-001", "R-002", "R-005", "R-011", "R-027", "R-036")


def _attempt_rows(rows: list[dict]) -> list[dict]:
    attempts = []
    for row in rows:
        for item in row.get("generation_attempt_history", []):
            attempts.append(
                {
                    "question_id": row["question_id"],
                    "attempt_no": item.get("attempt_count"),
                    "limiter_wait_seconds": (
                        round(item["rate_limit_wait_ms"] / 1000, 6)
                        if item.get("rate_limit_wait_ms") is not None
                        else None
                    ),
                    "request_started_monotonic_ms": item.get("request_started_monotonic_ms"),
                    "request_completed_monotonic_ms": item.get("request_completed_monotonic_ms"),
                    "http_status": item.get("http_status"),
                    "retry_after_seconds": item.get("retry_after_seconds"),
                    "retry_sleep_seconds": (
                        round(item["retry_delay_ms"] / 1000, 6)
                        if item.get("retry_delay_ms") is not None
                        else None
                    ),
                    "response_latency_ms": item.get("attempt_latency_ms"),
                    "attempt_outcome": item.get("outcome"),
                    "final_question_outcome": row.get("failure_stage"),
                }
            )
    if any(item["request_started_monotonic_ms"] is None for item in attempts):
        raise ValueError("P22 telemetry is incomplete; do not use this run for spacing validation")
    attempts.sort(key=lambda item: item["request_started_monotonic_ms"])
    origin = attempts[0]["request_started_monotonic_ms"] if attempts else 0
    previous_start = previous_end = None
    for item in attempts:
        start, end = item["request_started_monotonic_ms"], item["request_completed_monotonic_ms"]
        item["request_start_offset_ms"] = round(start - origin, 3)
        item["request_end_offset_ms"] = round(end - origin, 3) if end is not None else None
        item["previous_request_start_delta_ms"] = round(start - previous_start, 3) if previous_start is not None else None
        item["previous_request_end_delta_ms"] = round(start - previous_end, 3) if previous_end is not None else None
        previous_start, previous_end = start, end
    return attempts


def _spacing_summary(attempts: list[dict], min_interval_seconds: float) -> dict:
    deltas = [item["previous_request_start_delta_ms"] for item in attempts if item["previous_request_start_delta_ms"] is not None]
    minimum_ms = round(min_interval_seconds * 1000, 3)
    tolerance_ms = 5.0
    violations = [item for item in attempts if item["previous_request_start_delta_ms"] is not None and item["previous_request_start_delta_ms"] + tolerance_ms < minimum_ms]
    return {
        "policy_minimum_interval_ms": minimum_ms,
        "observed_minimum_start_delta_ms": min(deltas) if deltas else None,
        "spacing_policy_satisfied": not violations,
        "spacing_violation_count": len(violations),
        "spacing_violation_questions": [item["question_id"] for item in violations],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--execute", action="store_true", help="실제 HCX 비용이 발생한다.")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--minimum-interval-seconds",
        type=float,
        help="P23 pacing experiment only; does not modify .env or Agent logic.",
    )
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P22 invokes HCX. Specify --execute explicitly.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P22 requires GENERATOR_BACKEND=hcx and HCX-DASH-002")
    if args.minimum_interval_seconds is not None:
        if args.minimum_interval_seconds <= 0:
            raise ValueError("minimum interval must be positive")
        settings = replace(settings, hcx_min_interval_seconds=args.minimum_interval_seconds)
    questions = load_questions(args.questions)
    if args.phase == "smoke":
        questions = [question for question in questions if question.question_id in SMOKE_IDS]
        if tuple(question.question_id for question in questions) != SMOKE_IDS:
            raise ValueError("P22 smoke fixtures are missing or reordered")
    agent = ConditionalRoutingShadowAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=build_answer_generator(settings),
    )
    started = time.perf_counter()
    rows = evaluate_agent(TestClient(create_app(agent)), questions)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    attempts = _attempt_rows(rows)
    spacing = _spacing_summary(attempts, settings.hcx_min_interval_seconds)
    has_429 = any(item["http_status"] == 429 for item in attempts)
    payload = {
        "phase": args.phase,
        "model": settings.hcx_model,
        "question_ids": [question.question_id for question in questions],
        "duration_ms": duration_ms,
        "settings": {
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "max_retries": settings.max_retries,
        },
        "spacing": spacing,
        "http_429": sum(item["http_status"] == 429 for item in attempts),
        "retry_after_seen": sum(item["retry_after_seconds"] is not None for item in attempts),
        "full_run_permitted": not has_429 and spacing["spacing_policy_satisfied"],
        "attempts": attempts,
        "rows": rows,
    }
    output = args.output or ROOT / "data/diagnostics" / f"p22_{args.phase}_hcx.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("phase", "question_ids", "spacing", "http_429", "retry_after_seen", "full_run_permitted")}, ensure_ascii=False, indent=2))
    if args.phase == "smoke" and not payload["full_run_permitted"]:
        raise SystemExit("P22 smoke did not clear the provider/spacing gate; full run is blocked.")


if __name__ == "__main__":
    main()
