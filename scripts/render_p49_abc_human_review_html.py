"""Render the immutable A/B/C review packet as a readable local HTML sheet."""
from __future__ import annotations
import html, json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_regression_v1.json'
RECORDS=ROOT/'evaluation/fine_tuning/p49_draft_gold_training_records_v4.jsonl'
OUT=ROOT/'evaluation/fine_tuning/p49_hcx005_abc_p48_human_review_v1.html'
IDS={'positive_draft-p48-002','positive_draft-p48-005','positive_draft-p48-008','positive_draft-p48-009','positive_draft-p48-010','positive_draft-p48-011','positive_draft-p48-014'}
LANES={'A_hcx007':'A · HCX-007','B_hcx005':'B · untuned HCX-005','C_tuned_hcx005':'C · tuned HCX-005'}
CRITERIA=['직접 답변','근거 오독 없음','필수 사실 완전','인접 field 없음','근거 밖 claim 없음','outcome 행동 적절','문체·길이 자연스러움']
def e(s):return html.escape(str(s))
def main():
 if OUT.exists():raise SystemExit('immutable HTML review sheet already exists')
 abc=json.loads(SOURCE.read_text(encoding='utf-8'))
 records={x['record_id']:x for x in (json.loads(l) for l in RECORDS.read_text(encoding='utf-8').splitlines() if l.strip())}
 grouped=defaultdict(dict)
 for r in abc['results']:grouped[r['record_id']][r['lane']]=r
 cards=[]
 for i,rid in enumerate(sorted(grouped),1):
  record=records[rid]; quality=record['quality']
  answers=''.join(f"<section class='lane'><h3>{LANES[lane]}</h3><pre>{e(grouped[rid][lane].get('answer','[provider failure]'))}</pre></section>" for lane in LANES)
  checks=''.join(f"<label><input type='checkbox'> {c}</label>" for c in CRITERIA)
  cards.append(f"<article><h2>{i}. {e(rid.replace('positive_draft-','').upper())}</h2><p><b>질문</b> {e(record['question'])}</p><p><b>필수 사실</b> {e(' / '.join(quality.get('required_facts',[])))}</p><p><b>금지 claim</b> {e(' / '.join(quality.get('forbidden_claims',[])))}</p><div class='lanes'>{answers}</div><div class='checks'>{checks}</div><p>Overall: <select><option>선택</option><option>PASS</option><option>FAIL</option></select> Failure: <select><option>none</option><option>omission</option><option>misread</option><option>field_confusion</option><option>unsupported_expansion</option><option>outcome_behavior</option><option>wording</option></select></p><textarea placeholder='비교 메모'></textarea></article>")
 OUT.write_text("""<!doctype html><meta charset='utf-8'><title>P49 A/B/C Human Review</title><style>body{font:15px system-ui;max-width:1500px;margin:auto;padding:24px;background:#f6f7fb;color:#172033}article{background:#fff;border:1px solid #dce1ea;border-radius:12px;padding:18px;margin:18px 0}.lanes{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.lane{border:1px solid #dce1ea;border-radius:8px;padding:10px}pre{white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace}.checks{display:flex;flex-wrap:wrap;gap:10px;background:#f4f7fb;padding:10px;border-radius:8px}textarea{width:100%;height:64px}h1{margin-bottom:4px}@media(max-width:900px){.lanes{grid-template-columns:1fr}}</style><h1>P49 A/B/C Human Semantic Review</h1><p>P48 exposed regression · 7 questions × 3 lanes · 아래 체크는 브라우저 내 임시 입력이며 저장되지는 않습니다.</p>"""+''.join(cards),encoding='utf-8')
 print(OUT)
if __name__=='__main__':main()
