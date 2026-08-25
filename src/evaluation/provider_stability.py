"""P25-B provider telemetry를 품질 지표와 분리해 집계한다."""

from __future__ import annotations

from statistics import mean
from typing import Iterable


def attach_request_spacing(attempts: list[dict]) -> list[dict]:
    """실제 provider request start/end 기준의 이전 요청 간격을 계산한다."""

    ordered = sorted(attempts, key=lambda item: item.get("global_request_start_offset_ms") or -1)
    previous_start = previous_end = None
    for item in ordered:
        started = item.get("global_request_start_offset_ms")
        completed = item.get("global_request_completed_offset_ms")
        item["previous_request_start_delta_ms"] = (
            None if previous_start is None or started is None else round(started - previous_start, 3)
        )
        item["previous_request_end_delta_ms"] = (
            None if previous_end is None or started is None else round(started - previous_end, 3)
        )
        if started is not None:
            previous_start = started
        if completed is not None:
            previous_end = completed
    return ordered


def summarize_provider_attempts(attempts: Iterable[dict]) -> dict:
    attempts = list(attempts)
    statuses = [item.get("http_status") for item in attempts]
    start_deltas = [
        item["previous_request_start_delta_ms"]
        for item in attempts
        if item.get("previous_request_start_delta_ms") is not None
    ]
    timeout_count = sum(
        "timeout" in str(item.get("exception_type", "")).casefold()
        or "timed out" in str(item.get("exception_message", "")).casefold()
        for item in attempts
    )
    attempts_by_question: dict[str, list[dict]] = {}
    for item in attempts:
        attempts_by_question.setdefault(str(item.get("question_id", "")), []).append(item)
    provider_retry_attempts = 0
    provider_retry_exhaustion = 0
    for history in attempts_by_question.values():
        history.sort(key=lambda item: item.get("attempt_count") or 1)
        for previous, current in zip(history, history[1:]):
            previous_status = previous.get("http_status")
            if previous_status == 429 or (
                isinstance(previous_status, int) and previous_status >= 500
            ):
                provider_retry_attempts += 1
        terminal = history[-1]
        terminal_status = terminal.get("http_status")
        if terminal.get("outcome") == "failed" and (
            terminal_status == 429
            or (isinstance(terminal_status, int) and terminal_status >= 500)
        ):
            provider_retry_exhaustion += 1
    return {
        "provider_attempts": len(attempts),
        "http_200": sum(status == 200 for status in statuses),
        "http_429": sum(status == 429 for status in statuses),
        "http_5xx": sum(isinstance(status, int) and status >= 500 for status in statuses),
        "timeout": timeout_count,
        "retry_attempts": provider_retry_attempts,
        "retry_exhaustion": provider_retry_exhaustion,
        "retry_after_observed": sum(item.get("retry_after_seconds") is not None for item in attempts),
        "min_request_start_delta_ms": round(min(start_deltas), 3) if start_deltas else None,
        "mean_request_start_delta_ms": round(mean(start_deltas), 3) if start_deltas else None,
    }
