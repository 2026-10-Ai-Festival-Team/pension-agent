# -*- coding: utf-8 -*-
"""Freeze user-reviewed G3-A wording without modifying its Codex draft source."""
from __future__ import annotations
import json
import sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import build_p49_2h_4d_g3_bounded_residual as g3
from scripts import run_p49_2h_4c_execution_bridge as bridge
OUT=ROOT/'evaluation/fine_tuning/p49_2h_4d_g3a_bounded_anchor_human_approved_v1.jsonl'
TEXTS=['ISA 만기자금을 연금계좌로 옮길 예정인데, 내년에 적용될 추가 세액공제 한도가 얼마인지는 지금 자료에서 알 수 있어?','ISA 이전 자금을 계획하면서 향후 추가 세액공제 한도가 어느 수준으로 정해질지까지 현재 안내로 확인할 수 있어?','이 상품을 장기 보유하면 다음 위험등급이 몇 등급이 될지, 현재 공개된 자료만으로 미리 알 수 있어?','해당 상품의 위험등급이 앞으로 바뀔 경우 어느 등급으로 바뀌는지까지 지금 확인할 수 있어?','현재 이 상품의 위험등급을 보고 있는데, 향후 몇 등급으로 변경될지까지 이미 정해져 있는 정보야? 아니면 안 정해진거야?','이 상품에 가입하기 전에 앞으로 적용될 위험등급의 구체적인 등급도 알 수 있어?','이 상품 위험등급이 변경될 수 있다면, 실제 변경 시점이 언제인지도 현재 자료에서 확인할 수 있어?','해당 상품의 위험등급이 앞으로 어느 등급으로, 언제 변경될지까지 미리 알 수 있어?','이 상품을 계속 보유할 때 내년에 적용될 총보수율이 몇 퍼센트인지도 지금 알 수 있어?','해당 상품의 향후 총보수율을 얼마로 예상해야 하는지, 현재 안내에 구체적인 비율이 나와 있어?','이 상품의 미래 위험등급이 어느 정도가 될지, 다음 시점까지 현재 자료로 확인할 수 있어?','현재 안내만 보고 이 상품의 앞으로 위험등급을 구체적으로 예측할 수 있다고 봐도 돼?','이 상품을 장기 계획에 넣으려는데, 향후 위험등급의 구체적인 값까지 지금 자료에서 알 수 있어?','해당 상품의 미래 위험등급이 어느 수준이 될지, 또는 언제 바뀔지까지 이미 정해져 있어?','이 상품의 현재 자료는 미래 위험등급의 정확한 수치·시점까지 보여주는 자료야?','해당 상품의 현재 정보가 있으니 앞으로의 위험등급도 그대로 이어질 거라고 생각해도 돼?','이 상품을 비교 중인데, 제공 자료에 없는 미래 위험등급을 확정된 값처럼 판단하면 안 돼?','현재 안내로 이 상품의 위험등급이 바뀔 수 있다는 점은 알더라도, 향후 몇 등급이 될지까지는 알 수 없어?']
def approve(rows):
 if len(rows)!=18:return ValueError('expected 18')
 out=[]
 for row,text in zip(rows,TEXTS):
  r=deepcopy(row);a=r['bounded_linguistic_anchor']
  if a['authoring_status']!='drafted_by_codex':raise ValueError('non-draft')
  a['draft_anchor_question']=a['anchor_question'];a['anchor_question']=text;a['authoring_status']='human_written';a['human_review_status']='human_approved';a['approval_provenance']='user_supplied_rewrite_and_explicit_approval';r['g3_status']='human_written_human_approved';out.append(r)
 return out
def main():
 rows=approve(bridge.read_jsonl(g3.OUT_DRAFT)); pool=bridge.read_jsonl(g3.POOL); report=g3.preflight(rows,bridge.read_jsonl(bridge.SEMANTIC_REQUESTS),pool)
 if report['failures'] or not report['full_537_pool_dedup_pass']:raise SystemExit('approval preflight failed')
 if OUT.exists():raise FileExistsError(OUT)
 OUT.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8');print(json.dumps({'external_hcx_calls':0,'approved':18,'preflight_pass':report['preflight_pass'],'dedup':report['full_537_pool_dedup_pass']},ensure_ascii=False))
if __name__=='__main__':main()
