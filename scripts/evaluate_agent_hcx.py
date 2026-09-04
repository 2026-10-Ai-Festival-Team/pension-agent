"""Run the frozen 40-question dataset through the configured HyperCLOVA X Agent."""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from src.api.main import create_configured_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent, percentile
from src.evaluation.retrieval_dataset import load_questions


def mean(values):
    return round(statistics.mean(values), 3) if values else None


def summarize(rows):
    successful = [row for row in rows if row["generator_called"]]
    attempted = [row for row in rows if row["generator_attempted"]]
    parsed = [row for row in attempted if row["generation_model"]]
    generation_latencies = [row["generation_latency_ms"] for row in successful if row["generation_latency_ms"] is not None]
    usage = [row["generation_usage"] for row in successful if isinstance(row["generation_usage"], dict)]
    return {
        "question_count": len(rows),
        "api_success_rate": round(sum(row["status_code"] == 200 for row in rows) / len(rows), 3),
        "hcx_attempt_rate": round(len(attempted) / len(rows), 3),
        "hcx_json_parse_success_rate": round(len(parsed) / max(1, len(attempted)), 3),
        "citation_validation_rate": round(len(successful) / max(1, len(parsed)), 3),
        "hcx_accepted_answer_rate": round(len(successful) / max(1, len(attempted)), 3),
        "hcx_json_or_transport_failure_count": len(attempted) - len(parsed),
        "citation_rejection_count": len(parsed) - len(successful),
        "mean_total_latency_ms": mean([row["elapsed_ms"] for row in rows]),
        "p95_total_latency_ms": round(percentile([row["elapsed_ms"] for row in rows], 0.95), 3),
        "mean_generation_latency_ms": mean(generation_latencies),
        "p95_generation_latency_ms": round(percentile(generation_latencies, 0.95), 3) if generation_latencies else None,
        "usage_available_count": len(usage),
    }


def markdown(summary, rows):
    lines = ["# HyperCLOVA X E2E 기준선", "", "- 고정 검색 구성: 원본 Corpus 23,421청크, Simple BM25, `pension-v1`", "- 40개 질문을 실제 HCX 생성기와 `GET /answer` 계약으로 평가했다.", "- 입력·출력 토큰 사용량은 HCX 응답의 `usage` 제공 여부에 따라 진단 JSON에만 기록한다.", "", "## 결과", "", "| Metric | Value |", "|---|---:|"]
    for key, value in summary.items():
        lines.append(f"| {key} | {value if value is not None else 'N/A'} |")
    lines += ["", "## 단계별 결과", "", "| Stage | Count |", "|---|---:|"]
    for key, value in sorted(Counter(row["failure_stage"] for row in rows).items()):
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines) + "\n"


parser = argparse.ArgumentParser()
parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/agent_hcx_evaluation.json")
parser.add_argument("--report", type=Path, default=ROOT / "docs/agent_hcx_evaluation_report.md")
parser.add_argument("--diagnostics-only", action="store_true", help="Regenerate the report without calling HCX again.")
parser.add_argument("--request-delay-seconds", type=float, default=0, help="Delay only evaluator requests to avoid provider rate-limit contamination.")
args = parser.parse_args()

if args.diagnostics_only:
    rows = json.loads(args.output.read_text(encoding="utf-8"))["rows"]
else:
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx":
        raise SystemExit("HCX evaluation requires GENERATOR_BACKEND=hcx")
    rows = evaluate_agent(TestClient(create_configured_app(args.corpus, args.index, settings)), load_questions(args.questions), args.request_delay_seconds)
summary = summarize(rows)
if not args.diagnostics_only:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
args.report.write_text(markdown(summary, rows), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
