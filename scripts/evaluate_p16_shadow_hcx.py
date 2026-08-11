"""P16: baseline과 conditional-routing Shadow Agent의 실제 HCX E2E 비교."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent, percentile
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.factory import build_answer_generator
from src.orchestration.agent import PensionAgent
from src.orchestration.retrieval_service import build_frozen_retriever


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def _usage_total(rows: list[dict], names: tuple[str, ...]) -> int | None:
    values = []
    for row in rows:
        usage = row.get("generation_usage")
        if not isinstance(usage, dict):
            continue
        value = next((usage[name] for name in names if isinstance(usage.get(name), int)), None)
        if value is not None:
            values.append(value)
    return sum(values) if values else None


def _operational_summary(rows: list[dict]) -> dict:
    attempted = [row for row in rows if row.get("generator_attempted")]
    accepted = [row for row in rows if row.get("generator_called")]
    parsed = [row for row in attempted if row.get("generation_model")]
    histories = [history for row in attempted for history in row.get("generation_attempt_history", [])]
    statuses = [item.get("http_status") for item in histories]
    answerable = [row for row in rows if row["answerable"]]
    return {
        "total_questions": len(rows),
        "answerable_questions": len(answerable),
        "unsupported_questions": sum(not row["answerable"] for row in rows),
        "hcx_attempted": len(attempted),
        "pre_generation_rejection": sum(not row.get("generator_attempted") for row in rows),
        "http_429": sum(status == 429 for status in statuses),
        "retry_count": sum(item.get("outcome") == "retry" for item in histories),
        "retry_exhaustion": sum(
            row.get("generator_attempted")
            and not row.get("generator_called")
            and row.get("generation_error") == "GenerationError"
            for row in rows
        ),
        "json_or_schema_failure": sum(
            row.get("generator_attempted")
            and not row.get("generation_model")
            and row.get("generation_error") in {"GenerationError", "GenerationResponseError"}
            and all(item.get("http_status") != 429 for item in row.get("generation_attempt_history", []))
            for row in rows
        ),
        "citation_rejection": len(parsed) - len(accepted),
        "accepted_answers": len(accepted),
        "hcx_accepted_answer_rate": round(len(accepted) / max(1, len(attempted)), 3),
        "mean_latency_ms": _mean([row["elapsed_ms"] for row in rows]),
        "p50_latency_ms": round(percentile([row["elapsed_ms"] for row in rows], 0.5), 3),
        "p95_latency_ms": round(percentile([row["elapsed_ms"] for row in rows], 0.95), 3),
        "mean_generation_latency_ms": _mean([row["generation_latency_ms"] for row in accepted if row.get("generation_latency_ms") is not None]),
        "input_tokens": _usage_total(rows, ("inputTokens", "promptTokens", "input_tokens")),
        "output_tokens": _usage_total(rows, ("outputTokens", "completionTokens", "output_tokens")),
        "total_run_failure_stages": dict(Counter(row.get("failure_stage") for row in rows)),
    }


def _case_deltas(baseline: list[dict], shadow: list[dict]) -> list[dict]:
    by_id = {row["question_id"]: row for row in baseline}
    deltas = []
    for shadow_row in shadow:
        baseline_row = by_id[shadow_row["question_id"]]
        shadow_trace = shadow_row.get("generation_diagnostic") or {}
        deltas.append(
            {
                "question_id": shadow_row["question_id"],
                "baseline_outcome": baseline_row.get("failure_stage"),
                "shadow_outcome": shadow_row.get("failure_stage"),
                "baseline_semantic_label": "pending_manual_review",
                "shadow_semantic_label": "pending_manual_review",
                "shadow_route": shadow_row.get("route"),
                "baseline_evidence": baseline_row.get("retrieved_chunk_ids", []),
                "shadow_evidence": shadow_row.get("retrieved_chunk_ids", []),
                "baseline_citations": baseline_row.get("cited_chunk_ids", []),
                "shadow_citations": shadow_row.get("cited_chunk_ids", []),
                "baseline_latency_ms": baseline_row.get("elapsed_ms"),
                "shadow_latency_ms": shadow_row.get("elapsed_ms"),
                "delta": "pending_manual_review",
                "primary_reason": shadow_trace.get("citation_validation_reason") or "pending_manual_review",
            }
        )
    return deltas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--baseline-output", type=Path, default=ROOT / "data/diagnostics/p16_baseline_hcx.json")
    parser.add_argument("--shadow-output", type=Path, default=ROOT / "data/diagnostics/p16_shadow_hcx.json")
    parser.add_argument("--delta-output", type=Path, default=ROOT / "data/diagnostics/p16_case_deltas.jsonl")
    parser.add_argument("--cooldown-seconds", type=float, default=10.0)
    parser.add_argument("--execute", action="store_true", help="실제 HCX를 호출한다.")
    args = parser.parse_args()

    if not args.execute:
        raise SystemExit("P16은 실제 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P16은 HCX-DASH-002와 GENERATOR_BACKEND=hcx로만 실행합니다.")

    questions = load_questions(args.questions)
    baseline_agent = PensionAgent(
        build_frozen_retriever(args.corpus, args.index),
        build_answer_generator(settings),
    )
    baseline_started = time.perf_counter()
    baseline_rows = evaluate_agent(TestClient(create_app(baseline_agent)), questions)
    baseline_duration = round((time.perf_counter() - baseline_started) * 1000, 3)

    if args.cooldown_seconds:
        time.sleep(args.cooldown_seconds)

    shadow_agent = ConditionalRoutingShadowAgent(
        build_frozen_retriever(args.corpus, args.index),
        build_answer_generator(settings),
    )
    shadow_started = time.perf_counter()
    shadow_rows = evaluate_agent(TestClient(create_app(shadow_agent)), questions)
    shadow_duration = round((time.perf_counter() - shadow_started) * 1000, 3)

    for path in (args.baseline_output, args.shadow_output, args.delta_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    baseline_payload = {"variant": "baseline", "model": settings.hcx_model, "duration_ms": baseline_duration, "summary": _operational_summary(baseline_rows), "rows": baseline_rows}
    shadow_payload = {"variant": "conditional_shadow", "model": settings.hcx_model, "duration_ms": shadow_duration, "summary": _operational_summary(shadow_rows), "rows": shadow_rows}
    args.baseline_output.write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.shadow_output.write_text(json.dumps(shadow_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    deltas = _case_deltas(baseline_rows, shadow_rows)
    args.delta_output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in deltas), encoding="utf-8")
    print(json.dumps({"sequence": ["baseline", "cooldown", "conditional_shadow"], "cooldown_seconds": args.cooldown_seconds, "baseline": baseline_payload["summary"], "shadow": shadow_payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
