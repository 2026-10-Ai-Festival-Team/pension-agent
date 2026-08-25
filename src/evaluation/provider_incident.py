"""P25-B provider incident의 attempt telemetry를 재현 가능하게 분석한다."""

from __future__ import annotations

from collections import Counter
from typing import Iterable


def add_sliding_window_counts(
    attempts: Iterable[dict],
    *,
    windows_ms: tuple[int, ...] = (30_000, 60_000),
) -> list[dict]:
    """각 request start 시점의 최근 window 내 request 수를 추가한다."""

    ordered = sorted(
        (dict(attempt) for attempt in attempts),
        key=lambda item: item.get("global_request_start_offset_ms") or -1,
    )
    starts = [item.get("global_request_start_offset_ms") for item in ordered]
    for index, item in enumerate(ordered):
        item["request_no"] = index + 1
        current = starts[index]
        for window_ms in windows_ms:
            key = f"requests_in_previous_{window_ms // 1000}s"
            if current is None:
                item[key] = None
                continue
            item[key] = sum(
                previous is not None and 0 <= current - previous < window_ms
                for previous in starts[:index]
            )
    return ordered


def summarize_incident(
    attempts: Iterable[dict],
    *,
    configured_interval_seconds: float,
) -> dict:
    """429, retry limiter 통과 여부와 간격 위반을 품질 지표와 분리한다."""

    attempts = list(attempts)
    retries = [
        item
        for item in attempts
        if bool(item.get("retry_used")) or (item.get("attempt_count") or 1) > 1
    ]
    deltas = [
        item.get("previous_request_start_delta_ms")
        for item in attempts
        if item.get("previous_request_start_delta_ms") is not None
    ]
    configured_ms = configured_interval_seconds * 1000
    statuses = Counter(item.get("http_status") for item in attempts)
    first_429 = next((item for item in attempts if item.get("http_status") == 429), None)
    return {
        "configured_interval_ms": configured_ms,
        "attempt_count": len(attempts),
        "http_status_counts": {str(status): count for status, count in sorted(statuses.items(), key=lambda item: str(item[0]))},
        "retry_attempt_count": len(retries),
        "retries_with_limiter_telemetry": sum(
            item.get("rate_limit_wait_ms") is not None for item in retries
        ),
        "retry_after_observed": sum(item.get("retry_after_seconds") is not None for item in attempts),
        "spacing_violation_count": sum(delta < configured_ms for delta in deltas),
        "minimum_start_delta_ms": min(deltas) if deltas else None,
        "first_429": (
            {
                "question_id": first_429.get("question_id"),
                "attempt_count": first_429.get("attempt_count"),
                "start_offset_ms": first_429.get("global_request_start_offset_ms"),
                "previous_start_delta_ms": first_429.get("previous_request_start_delta_ms"),
                "requests_in_previous_30s": first_429.get("requests_in_previous_30s"),
                "requests_in_previous_60s": first_429.get("requests_in_previous_60s"),
            }
            if first_429
            else None
        ),
    }
