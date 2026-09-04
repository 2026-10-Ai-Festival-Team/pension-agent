"""Execute one fixed-pacing HCX rate-limit experiment without changing Agent policy."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from src.api.main import create_configured_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent, percentile
from src.evaluation.retrieval_dataset import load_questions


def summarize(rows, elapsed_seconds, pacing_seconds):
    attempted = [row for row in rows if row.get("generator_attempted")]
    parsed = [row for row in attempted if row.get("generation_model")]
    accepted = [row for row in attempted if row.get("generator_called")]
    history = [attempt for row in attempted for attempt in row.get("generation_attempt_history", [])]
    statuses = [attempt.get("http_status") for attempt in history]
    total_latencies = [row["elapsed_ms"] for row in rows]
    generation_latencies = [row["generation_latency_ms"] for row in accepted if row.get("generation_latency_ms") is not None]
    return {
        "pacing_seconds": pacing_seconds,
        "concurrency": 1,
        "retry_policy": "existing_max_retries_2_fixed_0.1s",
        "total_requests": len(rows),
        "hcx_attempted": len(attempted),
        "http_attempts": len(history),
        "http_429": sum(status == 429 for status in statuses),
        "retry_count": sum(max(0, len(row.get("generation_attempt_history", [])) - 1) for row in attempted),
        "retry_exhaustion": sum(not row.get("generation_model") and any(attempt.get("http_status") == 429 for attempt in row.get("generation_attempt_history", [])) for row in attempted),
        "other_http_errors": sum(isinstance(status, int) and status >= 400 and status != 429 for status in statuses),
        "json_parse_success": len(parsed),
        "citation_validation_pass": len(accepted),
        "accepted": len(accepted),
        "json_parse_success_rate": round(len(parsed) / max(1, len(attempted)), 3),
        "citation_validation_rate": round(len(accepted) / max(1, len(parsed)), 3),
        "accepted_answer_rate": round(len(accepted) / max(1, len(attempted)), 3),
        "mean_total_latency_ms": round(statistics.mean(total_latencies), 3),
        "p50_total_latency_ms": round(percentile(total_latencies, 0.5), 3),
        "p95_total_latency_ms": round(percentile(total_latencies, 0.95), 3),
        "mean_generation_latency_ms": round(statistics.mean(generation_latencies), 3) if generation_latencies else None,
        "p95_generation_latency_ms": round(percentile(generation_latencies, 0.95), 3) if generation_latencies else None,
        "run_elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_rpm": round(len(attempted) / max(elapsed_seconds, 0.001) * 60, 3),
    }


parser = argparse.ArgumentParser()
parser.add_argument("--run-id", required=True)
parser.add_argument("--pacing-seconds", type=float, required=True)
parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/hcx_rate_limit_runs.jsonl")
args = parser.parse_args()

load_dotenv(ROOT / ".env")
settings = GenerationSettings.from_env()
if settings.generator_backend != "hcx":
    raise SystemExit("HCX experiment requires GENERATOR_BACKEND=hcx")
started = time.perf_counter()
rows = evaluate_agent(
    TestClient(create_configured_app(ROOT / "data/parsed/chunks.jsonl", ROOT / "data/indexes/bm25/simple", settings)),
    load_questions(ROOT / "evaluation/retrieval_questions.jsonl"),
    args.pacing_seconds,
)
summary = summarize(rows, time.perf_counter() - started, args.pacing_seconds)
record = {"run_id": args.run_id, "run_type": "fixed_pacing", "summary": summary, "rows": rows}
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open("a", encoding="utf-8") as file:
    file.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps({"run_id": args.run_id, **summary}, ensure_ascii=False))
