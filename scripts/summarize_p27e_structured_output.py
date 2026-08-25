"""P27-E 두 batch를 합쳐 형식·운영 계약 결과만 보고한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, action="append", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.batch]
    rows = [row for payload in payloads for row in payload["rows"]]
    attempts = [attempt for payload in payloads for attempt in payload["attempt_telemetry"]]
    generator_rows = [row for row in rows if row.get("generator_attempted")]
    diagnostics = [row.get("generation_diagnostic") or {} for row in rows]
    schema_failures = sum(bool(row.get("generation_error")) for row in rows)
    empty_answer = sum("empty_answer" in item.get("response_contract_failures", []) for item in diagnostics)
    empty_citation = sum("empty_cited_chunk_ids" in item.get("response_contract_failures", []) for item in diagnostics)
    citation_failures = sum(
        bool(row.get("generator_attempted")) and not row.get("citation_valid") and not row.get("generation_error")
        for row in rows
    )
    status_codes = [attempt.get("http_status") for attempt in attempts]
    r019 = next(row for row in rows if row["question_id"] == "R-019")
    blocks = {row["question_id"]: row for row in rows if row["question_id"] in {"R-039", "R-040"}}
    api_success = sum(row.get("status_code") == 200 for row in rows)
    lines = [
        "# P27-E: Full-40 Native Structured Outputs 재인증",
        "",
        "P27-D에서 검증한 HCX-007 native Structured Outputs를 P24-B candidate retrieval/matcher, R-019 정책 수정, provenance/Financial Answer Policy, strict parser·citation validator, 6초 hard pacing과 함께 Full-40에 적용했다. 이 보고서는 semantic labeling 전 운영·출력 계약만 판정한다.",
        "",
        "## 결과",
        "",
        "| 항목 | 결과 |",
        "|---|---:|",
        f"| API 200 | {api_success}/{len(rows)} |",
        f"| HCX attempt | {len(generator_rows)} |",
        f"| HTTP 429 | {sum(status == 429 for status in status_codes)} |",
        f"| HTTP 5xx | {sum(isinstance(status, int) and status >= 500 for status in status_codes)} |",
        f"| Retry exhaustion | {sum(row.get('generation_error') == 'GenerationError' and any(item.get('http_status') in {429, 500, 502, 503, 504} for item in (row.get('generation_diagnostic') or {}).get('attempt_history', [])) for row in rows)} |",
        f"| JSON/schema failure | {schema_failures} |",
        f"| Empty answer | {empty_answer} |",
        f"| Empty citation | {empty_citation} |",
        f"| Citation validator failure | {citation_failures} |",
        f"| R-019 generator called | {r019.get('generator_called')} |",
        f"| R-039 safe block | {not blocks['R-039'].get('generator_attempted')} |",
        f"| R-040 safe block | {not blocks['R-040'].get('generator_attempted')} |",
        "",
        "새 answer hash 기반 semantic labeling은 별도 단계에서 수행한다. strict parser와 Fail-Closed validator는 재인증 중에도 완화하지 않았다.",
        "",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
