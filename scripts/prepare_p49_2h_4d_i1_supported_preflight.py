"""Render and strictly preflight all 48 I supported final host questions; no HCX."""
from __future__ import annotations
import argparse
import hashlib
import json, sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import build_p49_2h_4d_f_register_additive as f
from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.p49_2h_4d_e2_host_renderer import SUPPORTED_TOPICS
from scripts.p49_2h_4d_i1_supported_host_renderer import RENDERER_ID, TOPICS, render_host_question, surface_findings
from scripts.run_p49_2h_full_adapter import semantic_question_findings

POOL=ROOT/'evaluation/fine_tuning/p49_2h_4d_h_clarification_cumulative_comparison_pool_v1.jsonl'
RESIDUAL=ROOT/'evaluation/fine_tuning/p49_2h_4d_i_supported_residual_manifest_v1.jsonl'
OUT24=ROOT/'evaluation/fine_tuning/p49_2h_4d_i1_supported_renderer_expansion_manifest_v1.jsonl'
PRE24=ROOT/'evaluation/fine_tuning/p49_2h_4d_i1_supported_renderer_expansion_preflight_v1.json'
OUT48=ROOT/'evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_manifest_v2.jsonl'
PRE48=ROOT/'evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_preflight_v3.json'
PRE48_I1A=ROOT/'evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_preflight_v4_i1a.json'

def write(path:Path,data:Any,jsonl=False):
 if path.exists(): raise FileExistsError(path)
 path.write_text((''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in data) if jsonl else json.dumps(data,ensure_ascii=False,indent=2)+'\n'),encoding='utf-8')
def collision(d): return sum(len(d[k]) for k in ('exact_duplicates','normalized_duplicates','semantic_near_duplicates','frozen_seed_collisions'))
def plan(): return {x['coverage_cell']:x['deficit'] for x in bridge.read_jsonl(RESIDUAL)}
def binding(row,semantic):
 a=bridge.adapt_remediation_record(row,semantic)
 return {'canonical_requirement':row['canonical_requirement'],'required_answer_terms':list(a['answer_contract']['required_terms']),'required_literal_quotes':list(a['literal_evidence_quotes'])}
def build(source,semantic):
 rows=[]; seq=0
 for cell,n in sorted(plan().items()):
  matches=[x for x in source if x['coverage_cell']==cell and x['target_outcome']=='supported_answer']
  # Q1A's D14-Q01 aggregate cell has three product-subject source variants.
  # The approved I1 scope is limited to IRP early-withdrawal reasons, so the
  # four quota slots deliberately reuse only its canonical source with four
  # existing family controls; DC/pension-savings surfaces remain fail-closed.
  if cell == 'D14-Q01-supported_answer':
   matches=[x for x in matches if x['canonical_requirement']=='IRP.early_withdrawal.allowed_reasons']
  if not matches: raise ValueError(f'source shortage {cell}')
  for index in range(n):
   src=matches[index % len(matches)]
   seq+=1; row=f._row_from_source(src,seq,'supported_answer','formal',surface_variant_offset=seq-1)
   row.update(remediation_request_id=f'P49-2H-4D-I-SUP-{seq:04d}',i_source_manifest_request_id=src['remediation_request_id'],i_status='planned_zero_hcx',q1a_quota_cell=cell)
   if src['canonical_requirement'] in TOPICS: row['host_question_renderer']={'renderer_id':RENDERER_ID,'family':f.FAMILY_CYCLE[(seq-1)%len(f.FAMILY_CYCLE)]}; row['i_renderer_path']='I1_additive'
   elif src['canonical_requirement'] in SUPPORTED_TOPICS: row['i_renderer_path']='F_existing'
   else: raise ValueError(f'unsupported I requirement {src["canonical_requirement"]}')
   row['supported_answer_completeness']=binding(row,semantic); rows.append(row)
 if len(rows)!=48 or Counter(x['coverage_cell'] for x in rows)!=Counter(plan()): raise AssertionError('I allocation drift')
 return rows
def render(row,semantic):
 a=bridge.adapt_remediation_record(row,semantic); control=a['remediation_control']; rid=control['host_question_renderer']['renderer_id']
 if rid==RENDERER_ID: q=render_host_question(a['semantic_request'],control); extra=surface_findings(q,a['semantic_request'])
 else: _,q,extra=f.rendered_question(row,semantic)
 caller=bridge.caller_input_for(a,[]); findings=bridge.preservation_findings(row,a)+bridge.diversity_prompt_findings(row,caller)+bridge.field_boundary_prompt_findings(row,a,caller)+semantic_question_findings(q,a['semantic_request'])+extra
 return q,sorted(set(findings))
def preflight(rows,semantic,pool):
 failures=[]; virtual=[]; details=[]
 for row in rows:
  try:q,findings=render(row,semantic)
  except (KeyError,ValueError) as e:q='';findings=[f'renderer_fail_closed:{e}']
  virtual.append({'remediation_request_id':row['remediation_request_id'],'validation_status':'pass','question':q})
  details.append({'remediation_request_id':row['remediation_request_id'],'renderer_path':row['i_renderer_path'],'question':q,'findings':findings})
  if findings:failures.append(details[-1])
 d=bridge.full_set_dedup_audit(pool,virtual,bridge.read_jsonl(bridge.FROZEN_SEED))
 return {'stage':'P49-2H-4D-I1 renderer expansion + I 48 final host question strict preflight','external_hcx_calls':0,'comparison_pool_pass':len(pool),'requested':len(rows),'new_renderer_coverage':sum(x['i_renderer_path']=='I1_additive' for x in rows),'existing_renderer_coverage':sum(x['i_renderer_path']=='F_existing' for x in rows),'fail_closed':sum(any(x.startswith('renderer_fail_closed') for x in d['findings']) for d in details),'subject_preservation':sum(not any('subject' in x for x in d['findings']) for d in details),'canonical_requirement_preservation':sum(not any('scope' in x for x in d['findings']) for d in details),'field_scope_drift':sum(any('field' in x for x in d['findings']) for d in details),'semantic_drift':sum(bool(d['findings']) for d in details),'failures':failures,'questions':details,'full_set_dedup':d,'full_set_dedup_pass':collision(d)==0,'live_execution_allowed':len(rows)==48 and not failures and collision(d)==0}

def question_hash(rows):
 payload=''.join(f"{row['remediation_request_id']}\t{row.get('question', '')}\n" for row in rows)
 return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--repreflight-existing',action='store_true',help='rerun strict checks against the immutable 48-question I manifest')
 args=parser.parse_args()
 pool=[x for x in bridge.read_jsonl(POOL) if x.get('validation_status')=='pass']
 if len(pool)!=608: raise ValueError('I requires H 608 pool')
 semantic=bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
 if args.repreflight_existing:
  rows=bridge.read_jsonl(OUT48)
  if len(rows)!=48: raise ValueError('I1A requires exactly 48 existing I host-question rows')
  report=preflight(rows,semantic,pool)
  prior=json.loads(PRE48.read_text(encoding='utf-8'))
  prior_questions={row['remediation_request_id']:row['question'] for row in prior['questions']}
  current_questions={row['remediation_request_id']:row['question'] for row in report['questions']}
  report.update({'artifact_id':'P49-2H-4D-I1A-product-total-fee-validator-repair-v1','input_manifest':OUT48.name,'rendered_question_sha256':question_hash(report['questions']),'question_strings_changed':prior_questions != current_questions})
  write(PRE48_I1A,report)
 else:
  rows=build(bridge.read_jsonl(bridge.REMEDIATION_MANIFEST),semantic); report=preflight(rows,semantic,pool)
  write(OUT24,[x for x in rows if x['i_renderer_path']=='I1_additive'],True); write(PRE24,{**report,'scope':'I1 additive renderer 24 only','requested':24,'failures':[x for x in report['failures'] if x['renderer_path']=='I1_additive']})
  write(OUT48,rows,True); write(PRE48,report)
 print(json.dumps({'external_hcx_calls':0,'new_renderer_coverage':report['new_renderer_coverage'],'requested':report['requested'],'preflight_pass':report['live_execution_allowed']},ensure_ascii=False))
if __name__=='__main__':main()
