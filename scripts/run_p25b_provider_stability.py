"""P25-B: 고정 Agent 구성의 순차 HCX provider stability run."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.evaluation.provider_stability import attach_request_spacing, summarize_provider_attempts
from src.evaluation.provider_incident import add_sliding_window_counts
from src.evaluation.retrieval_dataset import load_questions
from src.generation.factory import build_answer_generator
from src.orchestration.agent import PensionAgent
from src.orchestration.retrieval_service import build_frozen_retriever


def _report(payload: dict) -> str:
    summary = payload["summary"]
    guard = payload.get("pacing_guard_seconds")
    hard_spacing = payload.get("hard_spacing_limiter", False)
    spacing_lines = (
        [
            f"- pacing guard: {guard}초",
            f"- limiter 예약 간격: {payload['effective_min_interval_seconds']}초",
            "- request-start 판정 기준: 설정 최소 간격 이상 (guard는 dispatch jitter 흡수용)",
        ]
        if hard_spacing
        else ["- 실제 start 간격의 hard guarantee: 이전 실행 limiter에서는 제공하지 않음"]
    )
    return "\n".join(
        [
            "# P25-B: 순차 HCX Provider 안정성",
            "",
            "P25-A 결과를 근거로 citation 계약을 변경하지 않고, 현재 기본 Agent의 기존 prompt·citation·Router/Gate·정책 구성을 그대로 사용해 단일 프로세스에서 순차 실행했다. 이 보고서는 semantic quality나 citation 품질을 평가하지 않는다.",
            "",
            "## 실행 조건",
            "",
            f"- 모델: `{payload['model']}`",
            f"- 요청 수: {payload['request_count']}",
            f"- HCX 호출 시도: {summary['generator_attempted']}",
            f"- 정책상 사전 차단: {summary['policy_blocked']}",
            f"- 전역 최소 간격 설정: {payload['min_interval_seconds']}초",
            *spacing_lines,
            "",
            "## Provider 원격 측정",
            "",
            f"- provider attempt: {summary['provider_attempts']}",
            f"- HTTP 200: {summary['http_200']}",
            f"- HTTP 429: {summary['http_429']}",
            f"- 5xx: {summary['http_5xx']}",
            f"- timeout: {summary['timeout']}",
            f"- retry attempt: {summary['retry_attempts']}",
            f"- retry exhaustion: {summary['retry_exhaustion']}",
            f"- Retry-After 관측: {summary['retry_after_observed']}",
            f"- 요청 시작 간격 최소/평균(ms): {summary['min_request_start_delta_ms']} / {summary['mean_request_start_delta_ms']}",
            "",
            "## 판정",
            "",
            "P25-B의 provider 안정성 통과 기준은 `retry exhaustion = 0`이다. 429와 5xx·timeout은 semantic 품질과 분리해 기록한다. 세부 attempt timestamp와 retry telemetry는 Git 제외 diagnostics에만 저장한다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p25b_provider_stability_raw.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p25b_provider_stability.md")
    parser.add_argument("--execute", action="store_true", help="실제 HCX 호출을 실행한다.")
    parser.add_argument("--summarize-existing", action="store_true", help="기존 diagnostics만 다시 집계한다.")
    parser.add_argument(
        "--minimum-interval-seconds",
        type=float,
        help="이번 실행에만 적용할 HCX 요청 최소 간격. .env는 변경하지 않는다.",
    )
    parser.add_argument(
        "--screening",
        action="store_true",
        help="P25-B2 후보 간격의 10~15문항 사전 검증을 허용한다.",
    )
    parser.add_argument(
        "--stop-on-429",
        action="store_true",
        help="screening에서 첫 429가 나오면 즉시 종료한다.",
    )
    args = parser.parse_args()
    if args.summarize_existing:
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        payload["attempt_telemetry"] = attach_request_spacing(payload["attempt_telemetry"])
        telemetry = summarize_provider_attempts(payload["attempt_telemetry"])
        payload["summary"] = {
            **telemetry,
            "generator_attempted": sum(row["generator_attempted"] for row in payload["rows"]),
            "policy_blocked": sum(not row["generator_attempted"] for row in payload["rows"]),
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(_report(payload), encoding="utf-8")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
        return
    if not args.execute:
        raise SystemExit("P25-B는 실제 HCX 호출을 수행합니다. 실행하려면 --execute를 지정하세요.")
    if args.limit < 30 and not args.screening:
        raise SystemExit("P25-B는 최소 30개 요청으로 실행해야 합니다.")
    if args.screening and not 10 <= args.limit <= 15:
        raise SystemExit("P25-B2 screening은 10~15문항만 실행해야 합니다.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx":
        raise SystemExit("P25-B에는 GENERATOR_BACKEND=hcx가 필요합니다.")
    if args.minimum_interval_seconds is not None:
        if args.minimum_interval_seconds <= 0:
            raise SystemExit("--minimum-interval-seconds는 0보다 커야 합니다.")
        settings = replace(settings, hcx_min_interval_seconds=args.minimum_interval_seconds)
    questions = load_questions(args.questions)[: args.limit]
    agent = PensionAgent(
        build_frozen_retriever(args.corpus, args.index),
        build_answer_generator(settings),
    )
    started = time.perf_counter()
    rows = []
    attempts = []
    for question in questions:
        question_started = time.perf_counter()
        result = agent.answer(question.question, top_k=10)
        trace = result["think_trace"]
        diagnostic = trace.get("generation_diagnostic") or {}
        history = diagnostic.get("attempt_history", [])
        contexts = result["retrieved_context"]
        context_characters = sum(len(item.text) for item in contexts)
        for item in history:
            attempt = dict(item)
            attempt["question_id"] = question.question_id
            attempt["question_characters"] = len(question.question)
            attempt["context_chunk_count"] = len(contexts)
            attempt["context_characters"] = context_characters
            attempt["global_request_start_offset_ms"] = (
                round((question_started - started) * 1000 + attempt["request_started_offset_ms"], 3)
                if attempt.get("request_started_offset_ms") is not None else None
            )
            attempt["global_request_completed_offset_ms"] = (
                round((question_started - started) * 1000 + attempt["request_completed_offset_ms"], 3)
                if attempt.get("request_completed_offset_ms") is not None else None
            )
            attempts.append(attempt)
        rows.append(
            {
                "question_id": question.question_id,
                "answerable": question.answerable,
                "generator_attempted": trace["generator_attempted"],
                "generator_called": trace["generator_called"],
                "assessment_reason": trace["assessment_reason"],
                "generation_error": trace.get("generation_error"),
                "attempt_count": len(history),
                "elapsed_ms": round((time.perf_counter() - question_started) * 1000, 3),
            }
        )
        if args.stop_on_429 and any(item.get("http_status") == 429 for item in history):
            break
    attempts = add_sliding_window_counts(attach_request_spacing(attempts), windows_ms=(30_000, 60_000, 120_000))
    telemetry = summarize_provider_attempts(attempts)
    summary = {
        **telemetry,
        "generator_attempted": sum(row["generator_attempted"] for row in rows),
        "policy_blocked": sum(not row["generator_attempted"] for row in rows),
    }
    payload = {
        "experiment": "P25-B2 provider pacing screening" if args.screening else "P25-B sequential provider stability",
        "hcx_called": True,
        "model": settings.hcx_model,
        "min_interval_seconds": settings.hcx_min_interval_seconds,
        "pacing_guard_seconds": settings.hcx_pacing_guard_seconds,
        "effective_min_interval_seconds": round(
            settings.hcx_min_interval_seconds + settings.hcx_pacing_guard_seconds,
            3,
        ),
        "hard_spacing_limiter": True,
        "request_count": len(rows),
        "total_duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "summary": summary,
        "rows": rows,
        "attempt_telemetry": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({"summary": summary, "duration_ms": payload["total_duration_ms"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
