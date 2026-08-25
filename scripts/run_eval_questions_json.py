"""eval_questions.json을 P31 v2 동결 경로로 실행한다."""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from dataclasses import replace
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from scripts.run_p26_candidate_hcx import _attempts
from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.provider_stability import summarize_provider_attempts
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever

def main():
    p=argparse.ArgumentParser(); p.add_argument('--execute',action='store_true'); p.add_argument('--questions',type=Path,default=ROOT/'eval_questions.json'); p.add_argument('--corpus',type=Path,default=ROOT/'data/parsed/chunks.jsonl'); p.add_argument('--index',type=Path,default=ROOT/'data/indexes/bm25/simple'); p.add_argument('--raw-output',type=Path,default=ROOT/'data/diagnostics/eval_questions_raw.json'); p.add_argument('--execution-output',type=Path,default=ROOT/'evaluation/eval_questions_execution.jsonl'); a=p.parse_args()
    if not a.execute: raise SystemExit('실제 HCX 비용이 발생합니다. --execute가 필요합니다.')
    questions=json.loads(a.questions.read_text(encoding='utf-8-sig'))
    if not isinstance(questions,list) or len(questions)!=30 or any(not x.get('id') or not x.get('question') for x in questions): raise SystemExit('eval_questions.json의 30개 id/question 형식을 확인하세요.')
    load_dotenv(ROOT/'.env'); settings=GenerationSettings.from_env()
    if settings.generator_backend!='hcx' or settings.hcx_model!='HCX-007': raise SystemExit('HCX-007 설정이 필요합니다.')
    settings=replace(settings,hcx_min_interval_seconds=6.0)
    generator=HyperClovaXGenerator(config=settings,prompt_builder=NativeStructuredOutputPromptBuilder(),rate_limiter=GlobalMinIntervalLimiter(6.0,guard_seconds=settings.hcx_pacing_guard_seconds))
    agent=P27DStructuredOutputAgent(retriever=build_frozen_retriever(a.corpus,a.index),generator=generator); client=TestClient(create_app(agent)); rows=[]; started=time.perf_counter()
    for q in questions:
        r=client.get('/answer',params={'question_id':q['id'],'question':q['question'],'top_k':10}); body=r.json() if r.status_code==200 else {}; trace=body.get('think_trace',{}); diagnostic=trace.get('generation_diagnostic') or {}
        rows.append({'question_id':q['id'],'category':q['category'],'subcategory':q['subcategory'],'difficulty':q['difficulty'],'question':q['question'],'expected_behavior':q['expected_behavior'],'gold_answer_points':q.get('gold_answer_points',[]),'required_evidence':q.get('required_evidence',[]),'must_not_include':q.get('must_not_include',[]),'status_code':r.status_code,'answer':body.get('answer',''),'answer_hash':hashlib.sha256(body.get('answer','').encode()).hexdigest(),'route':trace.get('route'),'evidence_sufficient':trace.get('evidence_sufficient'),'evidence_reason':trace.get('assessment_reason'),'missing_requirement_slots':trace.get('missing_requirement_slots',[]),'generator_attempted':trace.get('generator_attempted',False),'generator_called':trace.get('generator_called',False),'generation_error':trace.get('generation_error'),'citation_valid':(bool(trace.get('cited_chunk_ids')) and trace.get('generation_error') is None) if trace.get('generator_called') else True,'cited_chunk_ids':trace.get('cited_chunk_ids',[]),'selected_merged_evidence_ids':trace.get('selected_merged_evidence_ids',[]),'generation_attempt_history':diagnostic.get('attempt_history',[]),'semantic_correctness':'pending_manual_review','strict_useful':'pending_manual_review'})
    attempts=_attempts(rows); summary=summarize_provider_attempts(attempts); payload={'experiment':'eval_questions.json P31-v2 frozen execution','model':settings.hcx_model,'settings':{'native_structured_outputs':True,'thinking_effort':'none','minimum_interval_seconds':6.0,'strict_citation_validator':True},'duration_ms':round((time.perf_counter()-started)*1000,3),'provider_summary':summary,'rows':rows,'attempt_telemetry':attempts}
    a.raw_output.parent.mkdir(parents=True,exist_ok=True); a.execution_output.parent.mkdir(parents=True,exist_ok=True); a.raw_output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); a.execution_output.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
    print(json.dumps({'questions':len(rows),'generator_attempted':sum(x['generator_attempted'] for x in rows),'provider_summary':summary},ensure_ascii=False))
if __name__=='__main__': main()
