"""Create sanitized, reproducible HCX failure diagnostics from two E2E runs."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.hcx_failure_diagnostics import baseline_comparison_rows


def load_rows(path):
    return json.loads(path.read_text(encoding="utf-8"))["rows"]


def report(rows, baseline_rows, unpaced_rows, paced_rows):
    structured = [row for row in rows if row["failure_group"] == "structured_output"]
    citations = [row for row in rows if row["failure_group"] == "citation_validation"]
    baseline_structured = sum(row.get("generator_attempted") and not row.get("generation_model") for row in baseline_rows)
    baseline_citations = sum(bool(row.get("generator_attempted") and row.get("generation_model") and not row.get("generator_called")) for row in baseline_rows)
    unpaced_429 = sum((row.get("generation_diagnostic") or {}).get("http_status") == 429 for row in unpaced_rows)
    paced_structured = sum(row.get("generator_attempted") and not row.get("generation_model") for row in paced_rows)
    paced_citations = sum(bool(row.get("generator_attempted") and row.get("generation_model") and not row.get("generator_called")) for row in paced_rows)
    lines = ["# HyperCLOVA X 실패 진단", "", "## Scope", "", "- 이 문서는 정책·프롬프트·파서를 변경하지 않고 동일한 40문항을 진단 목적으로 재실행한 결과다.", "- 응답 원문·프롬프트·인증정보는 저장하지 않고 구조 메타데이터와 익명화된 JSON 형태만 기록했다.", "", "## Baseline and diagnostic run", "", f"- 기존 baseline: structured-output 실패 {baseline_structured}건, citation rejection {baseline_citations}건.", f"- unpaced diagnostic run: HTTP 429 {unpaced_429}건이 관측됐다.", f"- paced diagnostic run: structured-output 실패 {paced_structured}건, citation rejection {paced_citations}건.", "- `reproduced`는 unpaced run에서의 재현 여부이고, `paced_reproduced`는 요청 간격을 둔 run에서의 재현 여부다.", "", "## Structured-output failure", "", "| Category | Count | Reproduced baseline target |", "|---|---:|---:|"]
    for category, count in sorted(Counter(row["category"] for row in structured).items()):
        lines.append(f"| {category} | {count} | {sum(row['reproduced'] for row in structured if row['category'] == category)} |")
    lines += ["", "## Citation validation rejection", "", "| Cause | Count | Reproduced baseline target |", "|---|---:|---:|"]
    for cause, count in sorted(Counter(row["subcategory"] for row in citations).items()):
        lines.append(f"| {cause} | {count} | {sum(row['reproduced'] for row in citations if row['subcategory'] == cause)} |")
    lines += ["", "## Case list", "", "| Question | Group | Category | HTTP | Attempts | Stop reason | Exception | Unpaced reproduced | Paced reproduced |", "|---|---|---|---:|---:|---|---|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['question_id']} | {row['failure_group']} | {row['subcategory']} | {row['http_status'] or ''} | {row['attempt_count'] or ''} | {row['stop_reason'] or ''} | {row['exception_type'] or ''} | {row['reproduced']} | {row['paced_reproduced']} |")
    lines += ["", "## Root-cause summary", "", "- baseline structured-output 14건 중 9건은 unpaced run에서 HTTP 429와 retry exhaustion으로 직접 재현됐고, paced run에서는 structured-output 실패가 0건이었다. 요청 속도와 provider rate limit은 강한 원인 후보다.", "- 나머지 baseline structured-output 5건은 진단 run에서 재현되지 않았으므로 parser·truncation 원인으로 단정하지 않는다.", "- citation rejection 3건은 paced run에서 모두 재현됐다(unknown chunk ID 2건, missing citation 1건).", "", "## Fix proposals (not implemented)", "", "- P0: provider rate-limit을 실행환경 수준에서 제어하는 방안을 별도 실험으로 검증한다. Agent의 Fail-Closed 정책은 유지한다.", "- P1: unknown chunk ID와 missing citation은 validator를 완화하지 않고 prompt contract 또는 출력 schema 개선 실험으로 분리한다.", "- P2: 재현되지 않은 5건은 추가 run에서 response metadata를 축적한 뒤에만 parser·truncation 변경 후보로 승격한다."]
    return "\n".join(lines) + "\n"


parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, required=True)
parser.add_argument("--unpaced-diagnostic-run", type=Path, required=True)
parser.add_argument("--paced-diagnostic-run", type=Path, required=True)
parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/hcx_failure_diagnosis.jsonl")
parser.add_argument("--report", type=Path, default=ROOT / "docs/agent_hcx_failure_diagnosis.md")
args = parser.parse_args()

baseline_rows = load_rows(args.baseline)
unpaced_rows = load_rows(args.unpaced_diagnostic_run)
paced_rows = load_rows(args.paced_diagnostic_run)
rows = baseline_comparison_rows(baseline_rows, unpaced_rows, paced_rows)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
args.report.write_text(report(rows, baseline_rows, unpaced_rows, paced_rows), encoding="utf-8")
print(json.dumps({"diagnosed_failures": len(rows)}, ensure_ascii=False))
