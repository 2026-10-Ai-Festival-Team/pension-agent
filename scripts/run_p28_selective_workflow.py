"""P28-A backlog 8 + control 4 HCX selective workflow 파일럿."""
from __future__ import annotations
import argparse, json, sys
from dataclasses import replace
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.config.generation import GenerationSettings
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.experiments.p28_selective_workflow import FrozenEvidenceBundle, SelectiveWorkflow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.retrieval_service import build_frozen_retriever

BACKLOG=("R-006","R-010","R-019","R-034","R-011","R-033","R-035","R-038")
CONTROLS=("R-001","R-002","R-024","R-037")

def main():
 p=argparse.ArgumentParser(); p.add_argument('--execute',action='store_true'); p.add_argument('--output',type=Path,required=True); p.add_argument('--case-id',action='append',dest='case_ids'); args=p.parse_args()
 if not args.execute: raise SystemExit('P28-A는 실제 HCX 비용이 발생합니다. --execute가 필요합니다.')
 load_dotenv(ROOT/'.env'); settings=replace(GenerationSettings.from_env(),hcx_min_interval_seconds=6.0)
 if settings.generator_backend!='hcx' or settings.hcx_model!='HCX-007': raise SystemExit('HCX-007 설정이 필요합니다.')
 limiter=GlobalMinIntervalLimiter(6.0,guard_seconds=settings.hcx_pacing_guard_seconds)
 generator=HyperClovaXGenerator(config=settings,prompt_builder=NativeStructuredOutputPromptBuilder(),rate_limiter=limiter)
 agent=P27DStructuredOutputAgent(build_frozen_retriever(ROOT/'data/parsed/chunks.jsonl',ROOT/'data/indexes/bm25/simple'),generator)
 workflow=SelectiveWorkflow(generator); policy=FinancialAnswerPolicy(); questions={q.question_id:q for q in load_questions(ROOT/'evaluation/retrieval_questions.jsonl')}
 rows=[]
 requested=tuple(args.case_ids) if args.case_ids else BACKLOG+CONTROLS
 invalid_ids=sorted(set(requested)-set(questions))
 if invalid_ids: raise SystemExit(f'알 수 없는 question_id: {", ".join(invalid_ids)}')
 for qid in requested:
  q=questions[qid]; plan=agent.prepare(q.question,10); contexts=list(plan.contexts); req=tuple(s.name for s in plan.requirement_case.slots) if plan.requirement_case else ('질문에 직접 답변',)
  bundle=FrozenEvidenceBundle.from_contexts(contexts,req,policy)
  row={'question_id':qid,'case_role':'backlog' if qid in BACKLOG else 'control','route':plan.route.route,'requirements':list(req),'evidence_ids':[c.chunk_id for c in contexts],'allowed_primary_original_chunk_ids':list(bundle.allowed_primary_original_chunk_ids),'semantic_correctness':'pending_manual_review','requirement_coverage':'pending_manual_review','grounding':'pending_manual_review','strict_useful':'pending_manual_review'}
  try:
   result=workflow.execute(question=q.question,bundle=bundle,analysis=plan.analysis)
   row.update({'writer_answer':result.generated.answer,'cited_chunk_ids':result.generated.cited_chunk_ids,'writer_cited_chunk_ids':result.writer_cited_chunk_ids,'verifier_cited_chunk_ids':result.verifier_cited_chunk_ids,'repair_cited_chunk_ids':result.repair_cited_chunk_ids,'citation_valid':bundle.validates(result.generated.cited_chunk_ids),'verifier_verdict':result.verifier_verdict,'repaired':result.repaired,'hcx_calls':result.calls,'writer_diagnostic':result.generated.diagnostic,'verifier_diagnostic':result.verifier_diagnostic,'workflow_error':None})
  except Exception as error:
   row.update({'citation_valid':False,'repaired':False,'hcx_calls':None,'workflow_error':{'type':type(error).__name__,'message':str(error)}})
  rows.append(row)
 payload={'experiment':'P28-A selective workflow','model':settings.hcx_model,'fixed_conditions':{'same_evidence_only':True,'max_repair':1,'pacing_seconds':6,'native_structured_outputs':True},'rows':rows}
 args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'cases':len(rows),'repairs':sum(r['repaired'] for r in rows),'calls':sum(r['hcx_calls'] or 0 for r in rows),'citation_failures':sum(not r['citation_valid'] for r in rows),'workflow_errors':sum(r.get('workflow_error') is not None for r in rows)},ensure_ascii=False))
if __name__=='__main__': main()
