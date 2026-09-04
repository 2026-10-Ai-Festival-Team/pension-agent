"""Dry-run bridge audit for P49-2H-4C; never calls HCX."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'evaluation/fine_tuning/p49_2h_deficit_remediation_manifest_v1.jsonl'
OUT=ROOT/'evaluation/fine_tuning/p49_2h_4c_adapter_dry_run_v1.json'
IDS={f'P49-2H-4B-{n:04d}' for n in range(270,276)}|{f'P49-2H-4B-{n:04d}' for n in range(367,373)}
COMMON=('coverage_cell','target_outcome','canonical_requirement','subject','evidence_chunk_ids','source_ids','context_frame','query_form','register','length_band')
LANE={'clarification_required':('decision_target','scenario_context','missing_conditions','required_question_slots'),'bounded_answer':('unsupported_target','temporal_scope','target_type','concreteness_requirement','supported_requirements')}
def main():
 rows=[json.loads(x) for x in SRC.read_text(encoding='utf-8').splitlines() if x and json.loads(x)['remediation_request_id'] in IDS]
 audit=[]
 for r in rows:
  s=r['semantic_slots']; payload={**{k:r[k] for k in COMMON},**{k:s.get(k) for k in LANE[r['target_outcome']]},'comparison_pool':r['comparison_pool']}
  missing=[k for k in COMMON if payload.get(k)!=r.get(k)]+[k for k in LANE[r['target_outcome']] if payload.get(k)!=s.get(k)]
  audit.append({'request_id':r['remediation_request_id'],'outcome':r['target_outcome'],'payload':payload,'preservation':'pass' if not missing else 'fail','missing_or_changed':missing})
 result={'stage':'P49-2H-4C-1 adapter dry run','external_hcx_calls':0,'record_count':len(audit),'pass_count':sum(x['preservation']=='pass' for x in audit),'fail_count':sum(x['preservation']!='pass' for x in audit),'records':audit}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({k:result[k] for k in ('record_count','pass_count','fail_count')},ensure_ascii=False))
if __name__=='__main__': main()
