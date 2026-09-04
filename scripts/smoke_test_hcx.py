"""Run one evidence-rich HCX request without exposing credentials."""
import json, sys, time
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.api.main import create_configured_app
from src.config.generation import GenerationSettings

load_dotenv(ROOT / ".env")
settings=GenerationSettings.from_env()
missing=[name for name,value in (("HCX_API_KEY",settings.hcx_api_key),("HCX_MODEL",settings.hcx_model),("HCX_BASE_URL",settings.hcx_base_url)) if not value]
if settings.generator_backend != "hcx" or missing:
    raise SystemExit("HCX smoke test requires GENERATOR_BACKEND=hcx and: " + ", ".join(missing or ["GENERATOR_BACKEND=hcx"]))
app=create_configured_app(ROOT/"data/parsed/chunks.jsonl",ROOT/"data/indexes/bm25/simple",settings)
started=time.perf_counter(); result=app.state.agent.answer("DB형과 DC형의 적립금 운용 주체는 어떻게 다른가요?",10); elapsed=(time.perf_counter()-started)*1000
trace=result["think_trace"]; diagnostic=trace.get("generation_diagnostic") or {}
record={
    "question_id":"SMOKE-001",
    "elapsed_ms":round(elapsed,2),
    "generator_called":trace.get("generator_called",False),
    "generation_model":trace.get("generation_model"),
    "hcx_http_status":diagnostic.get("http_status"),
    "attempt_count":diagnostic.get("attempt_count"),
    "retry_used":diagnostic.get("retry_used",False),
    "generation_error":trace.get("generation_error"),
    "evidence_sufficient":trace.get("evidence_sufficient",False),
    "cited_chunk_ids":trace.get("cited_chunk_ids",[]),
    "answer_nonempty":bool(result["answer"].strip()),
}
if not record["generator_called"] or not 200 <= (record["hcx_http_status"] or 0) < 300:
    print(json.dumps(record,ensure_ascii=False))
    raise SystemExit("HCX smoke failed; inspect only the safe diagnostic fields above.")
path=ROOT/"data/diagnostics/hcx_smoke_result.json"; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(record,ensure_ascii=False))
