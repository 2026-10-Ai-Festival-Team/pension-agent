"""Build the zero-HCX G3-A bounded residual draft manifest from the 537 pool."""
from __future__ import annotations
import argparse, json, sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import build_p49_2h_4d_g1_bounded_anchor_inventory as g1
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.run_p49_2h_full_adapter import semantic_question_findings

POOL=ROOT/'evaluation/fine_tuning/p49_2h_4d_g2_cumulative_comparison_pool_v1.jsonl'
MANIFEST=bridge.REMEDIATION_MANIFEST
OUT_INV=ROOT/'evaluation/fine_tuning/p49_2h_4d_g3_bounded_residual_inventory_v1.json'
OUT_DRAFT=ROOT/'evaluation/fine_tuning/p49_2h_4d_g3a_bounded_anchor_drafts_v1.jsonl'
OUT_PREFLIGHT=ROOT/'evaluation/fine_tuning/p49_2h_4d_g3a_bounded_anchor_preflight_v1.json'
ALLOCATION={'D12-Q18-bounded_answer':2,'D17-Q12-bounded_answer':2,'D17-Q17-bounded_answer':2,'D18-Q17-bounded_answer':2,'D20-Q18-bounded_answer':2,'D30-Q12-bounded_answer':2,'D30-Q17-bounded_answer':6}
QUESTIONS={
'D12-Q18-bounded_answer':['ISA 만기자금을 옮길 계획인데, 내년에 적용될 추가 세액공제 한도가 얼마인지 지금 자료로 확인할 수 있나요?','ISA 만기자금 이전을 준비하면서, 앞으로 추가 세액공제 한도가 얼마로 정해질지는 아직 알 수 없는 건가요?'],
'D17-Q12-bounded_answer':['이 상품의 위험등급이 다음에 몇 등급이 될지, 현재 공개된 내용만으로 알 수 있나요?','장기 보유 전 이 상품 위험등급이 앞으로 어느 등급으로 바뀔지까지 미리 확인할 수 있나요?'],
'D17-Q17-bounded_answer':['해당 상품의 현재 위험등급을 보고 있는데, 향후 몇 등급이 될지까지 정해진 내용인가요?','이 상품을 보유한 뒤 위험등급이 바뀌면 다음 등급이 몇 등급인지 현재 자료에서 알 수 있나요?'],
'D18-Q17-bounded_answer':['이 상품의 위험등급이 변경될 수 있다면, 앞으로 실제 변경 시점은 언제인지도 확인할 수 있나요?','장기 투자하기 전에 해당 상품 위험등급이 어느 등급으로, 언제 변경될지까지 알 수 있을까요?'],
'D20-Q18-bounded_answer':['이 상품의 총보수율을 앞으로 얼마로 봐야 하는지, 내년 적용 비율까지 현재 자료에 나와 있나요?','해당 상품을 오래 보유하면 미래 총보수율이 몇 퍼센트가 될지 지금 알 수 있나요?'],
'D30-Q12-bounded_answer':['이 상품의 미래 위험등급이나 수익률이 어느 정도일지, 다음 시점까지 현재 자료로 확인할 수 있나요?','현재 자료를 보고 이 상품의 앞으로의 수익률이나 위험등급을 구체적으로 예측할 수 있다고 봐도 되나요?'],
'D30-Q17-bounded_answer':['이 상품을 자산계획에 넣으려는데, 향후 수익률과 위험등급의 구체 값은 어디까지 확인할 수 있어?','해당 상품은 다음 해에 위험등급이 어떻게 되고 수익률이 얼마일지까지 이미 공시돼 있나요?','이 상품의 현재 안내만으로 미래 수익률이나 위험등급의 정확한 수치·변경 시점을 알 수 있나요?','해당 상품을 비교 중인데, 지금 자료에 없는 앞으로의 수익률이나 위험등급까지 정해진 사실로 보면 안 되는 거죠?','이 상품의 미래 수익률과 위험등급이 언제 어떤 값이 될지는 자료에서 확인할 수 없는 항목인가요?','현재 설명을 보면 이 상품의 위험등급 변화 가능성은 알 수 있어도, 향후 몇 등급이 될지는 별도로 알 수 없는 건가요?']}
PROFILES=(('공시자료 검토 중','자료 범위 확인','근거 범위 점검','향후','미래 값이 이미 확정됐다는 전제','상황절+근거범위 확인','evidence_limit','general','medium'),('장기 보유 계획 중','계획 전제 점검','현재 정보와 미래 확정값 구분','앞으로','향후 시점에도 같은 값이라는 전제','계획절+정보공백 확인','planning_check','beginner','medium'),('운용 변경 안내 확인 중','확정 여부 확인','미래 수치 미확정 점검','다음','현재 정보가 미래 값을 보장한다는 전제','상황절+확정전제 확인','assumption_check','conversational','short'))

def build(manifest:list[dict[str,Any]])->list[dict[str,Any]]:
 by=defaultdict(list)
 for r in manifest: by[r['coverage_cell']].append(r)
 rows=[]; n=0
 for cell,count in ALLOCATION.items():
  if len(QUESTIONS[cell])!=count: raise ValueError('question allocation mismatch')
  for i,q in enumerate(QUESTIONS[cell]):
   n+=1; r=deepcopy(by[cell][i%len(by[cell])]); a,b,c,d,e,f,form,reg,length=PROFILES[i%len(PROFILES)]
   r['anchor_source_manifest_request_id']=r['remediation_request_id']; r['remediation_request_id']=f'P49-2H-4D-G3A-ANCHOR-{n:04d}'
   r.update(context_frame=a,query_form=form,register=reg,length_band=length)
   r['bounded_diversity_profile']={'profile_id':f'{cell}-g3a-{i+1:02d}','user_situation_frame':a,'speech_act':b,'information_gap_mode':c,'temporal_expression':d,'misconception_type':e,'sentence_shape':f}
   r['bounded_linguistic_anchor']={'anchor_id':f'P49-2H-4D-G3A-TEXT-{n:04d}','anchor_question':q,'linguistic_archetype':'G3-A Codex draft; actual human rewrite required','authoring_status':'drafted_by_codex','human_review_status':'human_review_required'}
   r['g3_status']='draft_pending_actual_human_rewrite'; rows.append(r)
 return rows
def preflight(rows,semantic,pool):
 failures=[]
 for r in rows:
  try:
   a=bridge.adapt_remediation_record(r,semantic); ci=bridge.caller_input_for(a,[x['question'] for x in pool]); f=bridge.preservation_findings(r,a)+bridge.diversity_prompt_findings(r,ci)+bridge.field_boundary_prompt_findings(r,a,ci)+semantic_question_findings(r['bounded_linguistic_anchor']['anchor_question'],a['semantic_request'])
   if f: failures.append({'remediation_request_id':r['remediation_request_id'],'findings':sorted(set(f))})
  except (KeyError,ValueError) as e: failures.append({'remediation_request_id':r['remediation_request_id'],'adapter_error':str(e)})
 provisional=[{'remediation_request_id':r['remediation_request_id'],'validation_status':'pass','question':r['bounded_linguistic_anchor']['anchor_question']} for r in rows]
 d=bridge.full_set_dedup_audit(pool,provisional,bridge.read_jsonl(bridge.FROZEN_SEED)); col=sum(len(d[k]) for k in ('exact_duplicates','normalized_duplicates','semantic_near_duplicates','frozen_seed_collisions'))
 return {'external_hcx_calls':0,'requested':len(rows),'requested_by_cell':dict(Counter(r['coverage_cell'] for r in rows)),'preflight_pass':len(rows)-len(failures),'failures':failures,'full_537_pool_dedup':d,'full_537_pool_dedup_pass':not col,'human_review_required':len(rows),'g3a_live_allowed':False,'g3a_live_block_reason':'all G3-A anchors require actual human rewrite and approval'}
def write(path,content):
 if path.exists(): raise FileExistsError(f'refusing overwrite: {path}')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
def main():
 p=argparse.ArgumentParser();p.add_argument('--inventory-output',type=Path,default=OUT_INV);p.add_argument('--draft-output',type=Path,default=OUT_DRAFT);p.add_argument('--preflight-output',type=Path,default=OUT_PREFLIGHT);args=p.parse_args()
 m=bridge.read_jsonl(MANIFEST); pool=bridge.read_jsonl(POOL); inv=g1.bounded_inventory(m,pool)
 if (len(pool),inv['bounded_current_unique_pass'],inv['bounded_deficit'])!=(537,67,35): p.error('expected frozen 537/67/35 baseline')
 residual={x['coverage_cell']:x['deficit'] for x in inv['cells'] if x['deficit']}
 if any(ALLOCATION[c]>residual[c] for c in ALLOCATION): p.error('G3-A allocation exceeds residual')
 rows=build(m); report=preflight(rows,bridge.read_jsonl(bridge.SEMANTIC_REQUESTS),pool)
 inv.update(stage='P49-2H-4D-G3 bounded residual recovery',comparison_pool_count=537,external_hcx_calls=0,g3a_allocation=ALLOCATION,g3b_remaining_by_cell={c:residual[c]-ALLOCATION.get(c,0) for c in residual},batch_08_original_manifest_allowed=False)
 write(args.inventory_output,json.dumps(inv,ensure_ascii=False,indent=2)+'\n');write(args.draft_output,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));write(args.preflight_output,json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'external_hcx_calls':0,'bounded_deficit':inv['bounded_deficit'],'g3a_records':len(rows),'preflight_pass':report['preflight_pass'],'dedup_pass':report['full_537_pool_dedup_pass']},ensure_ascii=False))
if __name__=='__main__':main()
