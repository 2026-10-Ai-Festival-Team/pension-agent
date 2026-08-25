from src.evaluation.provider_incident import add_sliding_window_counts, summarize_incident
from src.evaluation.provider_stability import attach_request_spacing, summarize_provider_attempts


def test_provider_summary_keeps_429_and_timeout_separate():
    attempts = attach_request_spacing(
        [
            {"question_id": "R-001", "global_request_start_offset_ms": 0, "global_request_completed_offset_ms": 100, "http_status": 200, "retry_used": False},
            {"question_id": "R-002", "global_request_start_offset_ms": 2000, "global_request_completed_offset_ms": 2100, "http_status": 429, "attempt_count": 1, "retry_used": False, "retry_after_seconds": 1},
            {"question_id": "R-002", "global_request_start_offset_ms": 4000, "global_request_completed_offset_ms": 4100, "http_status": 200, "attempt_count": 2, "retry_used": True},
            {"question_id": "R-003", "global_request_start_offset_ms": 6000, "global_request_completed_offset_ms": 6100, "http_status": None, "retry_used": False, "exception_type": "TimeoutError"},
        ]
    )
    summary = summarize_provider_attempts(attempts)

    assert attempts[1]["previous_request_start_delta_ms"] == 2000
    assert summary["http_429"] == 1
    assert summary["retry_attempts"] == 1
    assert summary["retry_exhaustion"] == 0
    assert summary["timeout"] == 1
    assert summary["retry_after_observed"] == 1


def test_incident_summary_counts_spacing_and_retry_limiter_telemetry():
    attempts = attach_request_spacing(
        [
            {"global_request_start_offset_ms": 0, "http_status": 200, "attempt_count": 1},
            {
                "global_request_start_offset_ms": 1945,
                "http_status": 429,
                "attempt_count": 2,
                "rate_limit_wait_ms": 1500,
            },
            {
                "global_request_start_offset_ms": 4000,
                "http_status": 200,
                "attempt_count": 2,
                "retry_used": True,
                "rate_limit_wait_ms": 1800,
            },
        ]
    )
    annotated = add_sliding_window_counts(attempts)
    summary = summarize_incident(annotated, configured_interval_seconds=2)

    assert annotated[1]["requests_in_previous_30s"] == 1
    assert annotated[1]["request_no"] == 2
    assert summary["spacing_violation_count"] == 1
    assert summary["retry_attempt_count"] == 2
    assert summary["retries_with_limiter_telemetry"] == 2
    assert summary["first_429"]["question_id"] is None
