"""P27-D A/B 실행 결과를 한국어 보고서로 요약한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _metric(rows: list[dict], key: str) -> str:
    return f"{sum(bool(row.get(key)) for row in rows)}/{len(rows)}"


def _case_rows(rows: list[dict]) -> list[str]:
    lines = []
    for question_id in sorted({row["question_id"] for row in rows}):
        subset = [row for row in rows if row["question_id"] == question_id]
        lines.append(
            f"| {question_id} | {_metric(subset, 'json_schema_success')} | "
            f"{sum(row['raw_content_has_prefix_prose'] for row in subset)} | "
            f"{sum(row['raw_content_has_markdown_fence'] for row in subset)} | "
            f"{_metric(subset, 'citation_validation_success')} |"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--structured", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    current, structured = _load(args.current), _load(args.structured)
    lines = [
        "# P27-D: HCX-007 Native Structured Outputs A/B",
        "",
        "P27-C에서 JSON 앞 설명문·Markdown fence 때문에 strict parser가 차단한 여섯 문항과 semantic control 네 문항을 같은 P26 candidate preparation 경로에서 2회씩 비교했다. parser와 Fail-Closed citation validator는 완화하지 않았다.",
        "",
        "## 고정 조건",
        "",
        "- 모델: `HCX-007`",
        "- pacing: 6초 hard global interval",
        "- A: 기존 JSON prompt + `thinking.effort=none`",
        "- B: `responseFormat.type=json` + JSON Schema, `thinking.effort=none` (실제 추론 비활성)",
        "- 대상: P27-C 형식 실패 6건 + semantic control 4건, 각 2회",
        "",
        "## 요약",
        "",
        "| Variant | JSON/schema | Citation validator | Prefix prose | Markdown fence | Empty answer | Empty citation |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| A: current prompt | {_metric(current, 'json_schema_success')} | {_metric(current, 'citation_validation_success')} | {sum(row['raw_content_has_prefix_prose'] for row in current)} | {sum(row['raw_content_has_markdown_fence'] for row in current)} | {sum(row['empty_answer'] for row in current)} | {sum(row['empty_citation_array'] for row in current)} |",
        f"| B: native Structured Outputs | {_metric(structured, 'json_schema_success')} | {_metric(structured, 'citation_validation_success')} | {sum(row['raw_content_has_prefix_prose'] for row in structured)} | {sum(row['raw_content_has_markdown_fence'] for row in structured)} | {sum(row['empty_answer'] for row in structured)} | {sum(row['empty_citation_array'] for row in structured)} |",
        "",
        "## B variant 문항별 결과",
        "",
        "| Question | JSON/schema | Prefix prose | Fence | Citation |",
        "|---|---:|---:|---:|---:|",
        *_case_rows(structured),
        "",
        "semantic correctness와 requirement coverage는 생성 답변 hash를 기준으로 별도 수동 검토한다. API schema는 형식을 보장할 뿐, citation ID의 허용 목록 적합성이나 금융 사실의 정확성을 보장하지 않으므로 기존 validator를 계속 적용했다.",
        "",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
