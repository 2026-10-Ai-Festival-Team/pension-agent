"""Run the frozen 40-question retrieval dataset through the FakeGenerator API."""
import argparse, json, sys
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.api.main import create_local_app
from src.evaluation.agent_evaluator import evaluate_agent, summarize_agent
from src.evaluation.retrieval_dataset import load_questions

p=argparse.ArgumentParser(); p.add_argument("--corpus",type=Path,default=Path("data/parsed/chunks.jsonl")); p.add_argument("--index",type=Path,default=Path("data/indexes/bm25/simple")); p.add_argument("--output",type=Path,default=Path("data/diagnostics/agent_e2e_baseline.json")); p.add_argument("--report",type=Path,default=Path("docs/agent_e2e_baseline_report.md")); a=p.parse_args()
rows=evaluate_agent(TestClient(create_local_app(a.corpus,a.index)),load_questions(Path("evaluation/retrieval_questions.jsonl"))); summary=summarize_agent(rows); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps({"summary":summary,"rows":rows},ensure_ascii=False,indent=2),encoding="utf-8")
lines=["# FakeGenerator E2E 기준선","", "- 고정 검색 구성: 원본 Corpus 23,421청크, Simple BM25, `pension-v1`", "- 40개 질문을 `GET /answer` 계약으로 호출했다.", "", "## 결과", "", "| Metric | Value |", "|---|---:|"]
for key,value in summary.items(): lines.append(f"| {key} | {value:.3f} |" if isinstance(value,float) else f"| {key} | {value} |")
lines += ["", "## 단계별 결과", "", "| Stage | Count |", "|---|---:|"]
from collections import Counter
for key,value in sorted(Counter(row.get("failure_stage") for row in rows).items()): lines.append(f"| {key} | {value} |")
a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
