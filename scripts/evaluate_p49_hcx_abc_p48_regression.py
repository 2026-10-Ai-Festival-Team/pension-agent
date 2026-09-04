"""Run frozen P48 generation-failure regression on HCX-007/005/tuned 005."""
from __future__ import annotations
import hashlib, json, os, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from scripts.create_p49_hcx005_tuning_task import write_once_or_verify
TASK="782y5g7f"; OUT=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_regression_v1.json'
PROMPT=json.loads((ROOT/'evaluation/fine_tuning/generator_prompt_final_v1.json').read_text(encoding='utf-8'))
SOURCE=ROOT/'evaluation/fine_tuning/p49_draft_gold_training_records_v4.jsonl'
IDS={'positive_draft-p48-002','positive_draft-p48-005','positive_draft-p48-008','positive_draft-p48-009','positive_draft-p48-010','positive_draft-p48-011','positive_draft-p48-014'}
LANES={'A_hcx007':'https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-007','B_hcx005':'https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005','C_tuned_hcx005':f'https://clovastudio.stream.ntruss.com/v3/tasks/{TASK}/chat-completions'}
def norm(x): return ''.join(str(x).lower().split())
def content(p):
 r=p.get('result',{}); m=r.get('message',{}) if isinstance(r,dict) else {}; return str(m.get('content') or p.get('message',{}).get('content') or (p.get('choices') or [{}])[0].get('message',{}).get('content') or '')
def body(lane, text):
 if lane=='A_hcx007':
  return {'messages':[{'role':'system','content':[{'type':'text','text':PROMPT['prompt']}]},{'role':'user','content':[{'type':'text','text':text}]}],'temperature':0,'maxCompletionTokens':1024}
 return {'messages':[{'role':'system','content':PROMPT['prompt']},{'role':'user','content':text}],'temperature':0,'maxTokens':1024}
def call(url,key,payload):
 req=Request(url,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json','X-NCP-CLOVASTUDIO-REQUEST-ID':str(uuid4())},method='POST')
 with urlopen(req,timeout=90) as res:return json.loads(res.read().decode())
def input_text(row):
 ev='\n\n'.join(f"[chunk_id: {x['chunk_id']}]\n{x['text']}" for x in row['direct_evidence'])
 return f"[질문]\n{row['question']}\n\n[canonical requirement]\n"+'\n'.join(row['selected_requirements'])+f"\n\n[선택된 직접 근거]\n{ev}\n\n[결과 유형]\nsupported_answer"
def assess(answer,row):
 q=row['quality']; anchors=q.get('evidence_anchors',[]); forbidden=q.get('forbidden_claims',[])
 return {'format_compliance':all(x in answer for x in ('[답변]','[근거]','[유의사항]')),'grounding_binding_present':'[근거]' in answer and bool(answer.split('[근거]',1)[1].strip() if '[근거]' in answer else ''),'citation_valid':any(x['chunk_id'] in answer for x in row['direct_evidence']),'required_anchor_omission':sum(norm(x) not in norm(answer) for x in anchors),'forbidden_claim_hit':sum(norm(x) in norm(answer) for x in forbidden),'semantic_manual_review_required':True}
def main():
 load_dotenv(ROOT/'.env')
 if OUT.exists():raise SystemExit('immutable A/B/C artifact exists')
 rows=[json.loads(x) for x in SOURCE.read_text(encoding='utf-8').splitlines() if x.strip()]; rows=[x for x in rows if x['record_id'] in IDS]
 if len(rows)!=7 or PROMPT['prompt_sha256']!='6c364cfc41367b7a5f4f4d521e4c2adaf1bd320182fb80bce69624c7625bb10a':raise RuntimeError('frozen regression authority mismatch')
 results=[]
 for lane,url in LANES.items():
  for row in rows:
   started=time.perf_counter()
   try:
    ans=content(call(url,os.environ['HCX_API_KEY'],body(lane,input_text(row))))
    results.append({'lane':lane,'record_id':row['record_id'],'answer':ans,'answer_sha256':hashlib.sha256(ans.encode()).hexdigest(),'latency_ms':round((time.perf_counter()-started)*1000,2),'provider_schema_failure':not bool(ans),**assess(ans,row)})
   except HTTPError as err:
    results.append({'lane':lane,'record_id':row['record_id'],'latency_ms':round((time.perf_counter()-started)*1000,2),'provider_schema_failure':True,'http_status':err.code})
 summary={}
 for lane in LANES:
  rs=[x for x in results if x['lane']==lane]; summary[lane]={'records':len(rs),'provider_schema_failure':sum(x['provider_schema_failure'] for x in rs),'format_compliance':sum(x.get('format_compliance',False) for x in rs),'citation_valid':sum(x.get('citation_valid',False) for x in rs),'required_anchor_omission':sum(x.get('required_anchor_omission',0) for x in rs),'forbidden_claim_hit':sum(x.get('forbidden_claim_hit',0) for x in rs),'mean_latency_ms':round(sum(x['latency_ms'] for x in rs)/len(rs),2)}
 artifact={'stage':'P49 A/B/C P48 exposed regression','boundary':'P48 development-exposed regression only; not Fresh P50','task_c':TASK,'prompt_sha256':PROMPT['prompt_sha256'],'records':[x['record_id'] for x in rows],'logical_requests':len(rows)*3,'lanes':{'A':'HCX-007','B':'untuned HCX-005','C':f'tuned HCX-005 task {TASK}'},'summary':summary,'results':results,'runtime_wiring_changed':False,'fresh_p50_called':False,'semantic_winner':'pending_human_review'}
 write_once_or_verify(OUT,(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
