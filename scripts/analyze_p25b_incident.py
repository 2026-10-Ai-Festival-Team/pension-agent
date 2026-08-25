"""P25-B1: 기존 provider telemetry를 재호출 없이 분석한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.provider_incident import add_sliding_window_counts, summarize_incident
from src.evaluation.provider_stability import attach_request_spacing


def make_report(payload: dict) -> str:
    summary = payload["summary"]
    first_429 = summary["first_429"]
    first_429_text = (
        f"`{first_429['question_id']}` attempt {first_429['attempt_count']} "
        f"(직전 start 간격 {first_429['previous_start_delta_ms']}ms, "
        f"직전 30초 요청 {first_429['requests_in_previous_30s']}건)"
        if first_429
        else "관측되지 않음"
    )
    return "\n".join(
        [
            "# P25-B1: Provider Rate-limit Incident Analysis",
            "",
            "## 범위",
            "",
            "P25-B의 기존 40문항 순차 실행 telemetry만 분석했다. HCX 재호출, prompt, retrieval, Router/Gate, citation validator, 금융 정책 변경은 수행하지 않았다.",
            "",
            "## 확인 결과",
            "",
            f"- 설정 최소 간격: {summary['configured_interval_ms'] / 1000:.3f}초",
            f"- 실제 start 간격 최솟값: {summary['minimum_start_delta_ms']}ms",
            f"- 설정 간격 미만 start 간격: {summary['spacing_violation_count']}건",
            f"- provider attempt: {summary['attempt_count']}건",
            f"- HTTP 상태: {summary['http_status_counts']}",
            f"- retry attempt: {summary['retry_attempt_count']}건; limiter wait telemetry 보존: {summary['retries_with_limiter_telemetry']}건",
            f"- Retry-After 관측: {summary['retry_after_observed']}건",
            f"- 첫 429: {first_429_text}",
            "",
            "## 원인 판단",
            "",
            "기존 limiter는 `time.monotonic()`을 사용했고 retry도 limiter를 거쳤다. 다만 미래 슬롯을 예약한 뒤 sleep을 한 번만 수행했으므로, OS의 조기 wake-up 뒤 실제 request start가 설정값보다 빨라질 수 있었다. P25-B의 1,944.91ms 최소 간격은 이 엄격 보장이 없었다는 직접 증거다.",
            "",
            "429가 긴 정상 응답 구간 이후에도 군집해 발생했으므로, 이 간격 오차만으로 28건 전체를 설명할 수는 없다. provider sliding-window/token quota 또는 동일 API key의 외부 사용 가능성이 남아 있다. P25-B 종료 후 로컬 프로세스를 확인했을 때 별도 평가 스크립트의 동시 HCX 호출은 확인되지 않았지만, 외부 프로세스·다른 환경의 같은 키 사용 여부는 이 telemetry만으로 확인할 수 없다.",
            "",
            "## 조치",
            "",
            "1. limiter를 sleep 후 남은 시간을 다시 계산하는 loop와 actual-start 기준 예약으로 교체했다.",
            "2. pacing guard를 설정화해 실제 request-start 간격이 `minimum interval + guard` 이상이 되도록 했다.",
            "3. P25-B2에서는 3초 후보를 10~15문항 screen으로 먼저 검증하고, 429가 발생하면 즉시 다음 후보(4초, 필요 시 5초)로 넘어간다.",
            "4. full sequential run의 필수 통과 기준은 retry exhaustion 0이다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/diagnostics/p25b_provider_stability_raw.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/diagnostics/p25b_incident_analysis.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs/p25b_incident_analysis.md",
    )
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    attempts = attach_request_spacing(source["attempt_telemetry"])
    attempts = add_sliding_window_counts(attempts)
    payload = {
        "experiment": "P25-B1 provider incident analysis",
        "source_experiment": source.get("experiment"),
        "summary": summarize_incident(
            attempts,
            configured_interval_seconds=source["min_interval_seconds"],
        ),
        "attempts": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(make_report(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
