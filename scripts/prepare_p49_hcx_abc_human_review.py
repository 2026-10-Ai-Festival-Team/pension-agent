"""Prepare, but never auto-decide, P48 A/B/C semantic human review."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_regression_v1.json'
RECORDS=ROOT/'evaluation/fine_tuning/p49_draft_gold_training_records_v4.jsonl'
OUT=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_human_review_v1.jsonl'
MANIFEST=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_human_review_manifest_v1.json'
CRITERIA=['direct_answer','misread_absent','required_facts_complete','adjacent_field_absent','evidence_only','outcome_behavior_natural','style_acceptable']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if OUT.exists() or MANIFEST.exists():raise SystemExit('immutable human review packet already exists')
 abc=json.loads(SOURCE.read_text(encoding='utf-8'))
 source={x['record_id']:x for x in (json.loads(l) for l in RECORDS.read_text(encoding='utf-8').splitlines() if l.strip())}
 rows=[]
 for index,result in enumerate(abc['results'],1):
  record=source[result['record_id']]; q=record['quality']
  rows.append({'review_id':f'P49-ABC-HR-{index:03d}','regression_record_id':result['record_id'],'blind_lane':f'blind_{index%3+1}','question':record['question'],'canonical_requirement':record['selected_requirements'],'selected_evidence':[x['text'] for x in record['direct_evidence']],'required_facts':q.get('required_facts',[]),'forbidden_claims':q.get('forbidden_claims',[]),'answer':result.get('answer',''),'answer_sha256':result.get('answer_sha256'),'review_criteria':{x:'pending_human_review' for x in CRITERIA},'overall':'pending_human_review','reviewer':'','review_note':''})
 OUT.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
 MANIFEST.write_text(json.dumps({'stage':'P49 A/B/C P48 human semantic review packet','source':SOURCE.name,'source_sha256':sha(SOURCE),'records':len(rows),'criteria':CRITERIA,'semantic_decision':'human_only_pending','runtime_wiring_changed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'records':len(rows),'human_decision':'pending'},ensure_ascii=False))
if __name__=='__main__':main()
