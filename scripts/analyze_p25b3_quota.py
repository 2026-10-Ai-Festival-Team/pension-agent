"""P25-B3: pacing screen의 429 위치와 quota-window 후보를 비교한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.provider_incident import add_sliding_window_counts, summarize_incident
from src.evaluation.provider_stability import attach_request_spacing


def _candidate(path: Path) -> dict:
    source = json.loads(path.read_text(encoding="utf-8"))
    attempts = add_sliding_window_counts(
        attach_request_spacing(source["attempt_telemetry"]),
        windows_ms=(30_000, 60_000, 120_000),
    )
    rate_limits = [
        {
            "request_no": item["request_no"],
            "question_id": item.get("question_id"),
            "attempt_no": item.get("attempt_count"),
            "previous_start_delta_ms": item.get("previous_request_start_delta_ms"),
            "requests_in_previous_30s": item.get("requests_in_previous_30s"),
            "requests_in_previous_60s": item.get("requests_in_previous_60s"),
            "requests_in_previous_120s": item.get("requests_in_previous_120s"),
            "request_payload_bytes": item.get("request_payload_bytes"),
            "context_characters": item.get("context_characters"),
            "usage": item.get("usage"),
        }
        for item in attempts
        if item.get("http_status") == 429
    ]
    return {
        "path": str(path.relative_to(ROOT)),
        "min_interval_seconds": source["min_interval_seconds"],
        "request_count": source["request_count"],
        "summary": summarize_incident(
            attempts,
            configured_interval_seconds=source["min_interval_seconds"],
        ),
        "provider_retry_exhaustion": source.get("summary", {}).get("retry_exhaustion"),
        "rate_limit_events": rate_limits,
        "attempts": attempts,
    }


def _event_text(candidate: dict) -> str:
    if not candidate["rate_limit_events"]:
        return "없음"
    return ", ".join(
        f"#{event['request_no']} {event['question_id']} (직전 {event['previous_start_delta_ms']}ms, "
        f"30초 {event['requests_in_previous_30s']}건/60초 {event['requests_in_previous_60s']}건)"
        for event in candidate["rate_limit_events"]
    )


def _report(candidates: list[dict]) -> str:
    rows = [
        "# P25-B3: HCX Quota Isolation",
        "",
        "## 범위",
        "",
        "P25-B2의 3·4·5초 pacing screen telemetry를 재분석했다. Agent, retrieval, prompt, citation, Router/Gate, 금융 정책은 변경하지 않았으며 HCX를 새로 호출하지 않았다.",
        "",
        "## 429 위치",
        "",
        "| 설정 간격 | 429 위치 | HTTP 429 | retry exhaustion |",
        "|---:|---|---:|---:|",
    ]
    for candidate in candidates:
        summary = candidate["summary"]
        rows.append(
            f"| {candidate['min_interval_seconds']}초 | {_event_text(candidate)} | "
            f"{summary['http_status_counts'].get('429', 0)} | {candidate['provider_retry_exhaustion']} |"
        )
    rows.extend(
        [
            "",
            "## 판단",
            "",
            "3초와 4초는 모두 request #12(R-012)에서 429가 시작됐다. 5초는 request #12(R-010)에서 단발 429가 발생했으나 재시도로 복구됐다. 각 429 직전 request-start 간격은 해당 설정값 이상이어서, 단순 start-spacing 위반만으로 설명할 수 없다.",
            "",
            "P25-B2 기존 telemetry에는 prompt/context 크기와 API usage가 아직 기록되지 않아 token/resource quota를 판별할 수 없다. P25-B3 이후 새 실행에는 payload byte 수, context 문자 수, usage, 30/60/120초 요청량을 attempt마다 저장한다.",
            "",
            "로컬 process 점검은 단일 실행 프로세스 외 동시 평가 스크립트를 확인하지 못했지만, 동일 credential이 다른 환경에서 사용되는지 여부는 로컬 telemetry로 증명할 수 없다. 전용 credential을 사용할 수 있다면 다음 6초 screen은 그 credential과 단일 프로세스로 실행해야 한다.",
            "",
            "## 다음 gate",
            "",
            "6초에서 10~15문항을 screen한다. 429가 한 번이라도 나오면 full run으로 승격하지 않고 provider quota/credential 격리를 우선 확인한다. 429=0인 경우에만 38문항 full sequential stability run을 검토한다.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        default=[
            ROOT / "data/diagnostics/p25b2_3s_screen_raw.json",
            ROOT / "data/diagnostics/p25b2_4s_screen_raw.json",
            ROOT / "data/diagnostics/p25b2_5s_screen_raw.json",
        ],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/diagnostics/p25b3_quota_isolation.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs/p25b3_quota_isolation.md",
    )
    args = parser.parse_args()
    candidates = [_candidate(path) for path in args.inputs]
    payload = {"experiment": "P25-B3 quota isolation", "candidates": candidates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(candidates), encoding="utf-8")
    print(
        json.dumps(
            [
                {
                    "interval_seconds": candidate["min_interval_seconds"],
                    "rate_limit_events": candidate["rate_limit_events"],
                }
                for candidate in candidates
            ],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
