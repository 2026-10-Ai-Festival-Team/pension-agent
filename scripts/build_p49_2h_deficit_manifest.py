"""Build P49-2H-4B remediation requests without external model calls."""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.p49_2h_register_taxonomy import REGISTER_ALLOCATION_CYCLE, register_for_index

SEMANTIC = ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_requests_v3.jsonl"
VALIDATED = ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_validated_v5.jsonl"
OUT = ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_manifest_v1.jsonl"
SUMMARY = ROOT / "evaluation/fine_tuning/p49_2h_deficit_remediation_manifest_v1.json"
TARGETS = {"supported_answer": 390, "clarification_required": 108, "bounded_answer": 102}
FRAMES = ("이직/퇴직 직후", "이전 신청 중", "상담 전 확인", "상품 비교 전 확인", "세액공제 계산 전", "서류 준비 중")
FORMS = ("direct", "confirmation", "misconception", "conditional", "numeric")
# Applied only if a new immutable manifest version is deliberately built.  The
# already-published v1 manifest is never regenerated or overwritten.
REGISTERS = REGISTER_ALLOCATION_CYCLE
LENGTHS = ("short", "medium")

def read(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
def allocate(counts, total):
    base=sum(counts.values()); raw={k:v*total/base for k,v in counts.items()}; out={k:int(v) for k,v in raw.items()}
    for k in sorted(raw, key=lambda k:(raw[k]-out[k], k), reverse=True)[:total-sum(out.values())]: out[k]+=1
    return out

def main():
    semantic, validated = read(SEMANTIC), read(VALIDATED)
    pass_counts=Counter((r["outcome"],r["coverage_cell"]) for r in validated if r["validation_status"]=="pass")
    cells=defaultdict(list)
    for r in semantic: cells[r["target_outcome"],r["coverage_cell"]].append(r)
    rows=[]; seq=1
    for lane,target in TARGETS.items():
        lane_cells={cell:len(items) for (outcome,cell),items in cells.items() if outcome==lane}
        allocation=allocate(lane_cells,target)
        for cell,target_count in allocation.items():
            current=pass_counts[lane,cell]; deficit=max(0,target_count-current)
            for offset in range(deficit):
                source=cells[lane,cell][offset%len(cells[lane,cell])]
                rows.append({"remediation_request_id":f"P49-2H-4B-{seq:04d}","coverage_cell":cell,"target_outcome":lane,"current_pass_count":current,"target_count":target_count,"deficit_count":deficit,"canonical_requirement":source["host_question_contract"].get("canonical_requirement"),"subject":source["host_question_contract"]["subject"],"evidence_chunk_ids":source["evidence_chunk_ids"],"source_ids":source["source_ids"],"semantic_slots":source["host_question_contract"],"context_frame":FRAMES[offset%len(FRAMES)],"query_form":FORMS[offset%len(FORMS)],"register":register_for_index(offset),"length_band":LENGTHS[offset%len(LENGTHS)],"comparison_pool":"p49_2h_full_semantic_validated_v5:pass_only"}); seq+=1
    # Cell-level target allocation is authoritative.  Its total can exceed the
    # outcome-only 467 lower bound when PASS records are concentrated in cells
    # whose allocated target is already satisfied.
    OUT.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
    SUMMARY.write_text(json.dumps({"stage":"P49-2H-4B Deficit Manifest","external_hcx_calls":0,"immutable_comparison_pool_pass":133,"targets":TARGETS,"minimum_deficit":len(rows),"rows":len(rows),"accepted_records":0,"training_export_allowed":False,"tuning_allowed":False},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rows":len(rows),"targets":TARGETS},ensure_ascii=False))
if __name__ == "__main__": main()
