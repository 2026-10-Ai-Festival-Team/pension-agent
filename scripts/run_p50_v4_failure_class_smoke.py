"""One HCX-007 smoke per repaired Fresh P50 v4 primary failure class."""
from __future__ import annotations
import json
from pathlib import Path
import sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.run_fresh_p50_v2_final_holdout import _evaluate
from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS,_settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.generation.versioned_generator_prompt import load_generator_prompt
from src.orchestration.retrieval_service import build_frozen_retriever
HOLDOUT=ROOT/'question_bank/holdouts/fresh_p50_final_holdout_v4.jsonl'; OUT=ROOT/'evaluation/p50_v4_failure_class_smoke_v1.json'; CK=ROOT/'evaluation/.p50_v4_failure_class_smoke_checkpoint_v1.jsonl'
IDS={'P50V4-012','P50V4-023','P50V4-038','P50V4-041','P50V4-047'}
def main():
 if OUT.exists(): raise RuntimeError('smoke artifact exists; no duplicate HCX calls')
 rows=[json.loads(x) for x in HOLDOUT.read_text().splitlines() if x.strip() and json.loads(x)['id'] in IDS]
 done={json.loads(x)['id']:json.loads(x) for x in CK.read_text().splitlines() if x.strip()} if CK.exists() else {}
 s=_settings(); lim=GlobalMinIntervalLimiter(PACING_SECONDS,guard_seconds=s.hcx_pacing_guard_seconds)
 agent=DirectRequirementE2EAgent(ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=s,rate_limiter=lim)),ScopedFrontendPreparationShadow(build_frozen_retriever(ROOT/'data/parsed/chunks.jsonl',ROOT/'data/indexes/bm25/simple')),HyperClovaXGenerator(config=s,rate_limiter=lim),prompt_contract=load_generator_prompt('generator_prompt_final_v2_1'))
 for row in rows:
  if row['id'] in done: continue
  t=time.perf_counter(); done[row['id']]=_evaluate(row,agent.answer(row['question']),(time.perf_counter()-t)*1000)
  with CK.open('a') as f:f.write(json.dumps(done[row['id']],ensure_ascii=False)+'\n')
 outputs=[done[row['id']] for row in rows]
 failures=sorted({x for o in outputs for x in o['failure_classes']})
 artifact={'experiment':'P50 v4 class smoke','prompt_sha256':'05763afaa082af98832a04d29001a9d2ee1f353308cd4cc8e651e3b15b9c83a8','outputs':outputs,'summary':{'record_count':len(outputs),'pass_count':sum(o['strict_pass'] for o in outputs),'failure_classes':failures,'decision':'GO' if not failures else 'NO_GO'}}
 OUT.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n');print(json.dumps(artifact['summary'],ensure_ascii=False))
if __name__=='__main__':main()
