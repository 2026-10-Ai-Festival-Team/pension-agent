"""동결된 P27-E answer hash에 대한 1차 수동 semantic review를 기록한다."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES = {
    "R-006": ("partial", "partial", "fully_supported", "requirement_omission"),
    "R-010": ("partial", "partial", "fully_supported", "requirement_omission"),
    "R-011": ("incorrect", "missing", "fully_supported", "answer_irrelevance"),
    "R-019": ("correct", "partial", "fully_supported", "requirement_omission"),
    "R-033": ("incorrect", "missing", "unsupported", "product_field_confusion"),
    "R-034": ("partial", "partial", "fully_supported", "numeric_confusion"),
    "R-035": ("incorrect", "missing", "partially_supported", "product_field_confusion"),
    "R-038": ("incorrect", "missing", "fully_supported", "answer_irrelevance"),
}

def main():
    rows = [json.loads(line) for path in (ROOT / "evaluation/p27e_batch_01_execution.jsonl", ROOT / "evaluation/p27e_batch_02_execution.jsonl") for line in path.read_text(encoding="utf-8").splitlines()]
    labels = []
    for row in rows:
        qid = row["question_id"]
        if qid in {"R-039", "R-040"}:
            semantic, coverage, grounding, policy, reason = "not_evaluable", "missing", "unsupported", "correct", "policy_block"
        elif qid in FAILURES:
            semantic, coverage, grounding, reason = FAILURES[qid]
            policy = "n/a"
        else:
            semantic, coverage, grounding, policy, reason = "correct", "full", "fully_supported", "n/a", None
        labels.append({"question_id": qid, "answer_hash": row["answer_hash"], "semantic_correctness": semantic, "requirement_coverage": coverage, "grounding": grounding, "policy_behavior": policy, "strict_useful": semantic == "correct" and coverage == "full" and grounding == "fully_supported" and policy != "incorrect", "failure_reason": reason})
    payload = {"dataset": "P27-E Native Structured Outputs 실행 결과의 수동 의미 품질 라벨", "source_execution_files": ["evaluation/p27e_batch_01_execution.jsonl", "evaluation/p27e_batch_02_execution.jsonl"], "labels": labels}
    (ROOT / "evaluation/p27e_semantic_labels.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    answerable = [x for x in labels if x["question_id"] not in {"R-039", "R-040"}]
    compound = [x for x, row in zip(labels, rows) if row["route"] == "compound"]
    p24b = [x for x in labels if x["question_id"] in {"R-010", "R-024", "R-028", "R-037"}]
    report = "\n".join(["# P27-E-S: Native Structured Outputs 의미 품질 라벨링", "", f"- Strict E2E Useful: **{sum(x['strict_useful'] for x in answerable)}/{len(answerable)}**", f"- 생성 답변 의미 정확성: **{sum(x['semantic_correctness'] == 'correct' for x in answerable)}/{len(answerable)}**", f"- Compound Strict Useful: **{sum(x['strict_useful'] for x in compound)}/{len(compound)}**", f"- P24-B 대상 Strict Useful: **{sum(x['strict_useful'] for x in p24b)}/{len(p24b)}**", "", "## 비교", "", "| 지표 | P26 | P27-E |", "|---|---:|---:|", f"| Strict E2E Useful | 28/38 | {sum(x['strict_useful'] for x in answerable)}/38 |", "| Compound Strict Useful | 7/11 | " + f"{sum(x['strict_useful'] for x in compound)}/{len(compound)} |", "| P24-B target | 3/4 | " + f"{sum(x['strict_useful'] for x in p24b)}/{len(p24b)} |", "", "P27-E는 형식·인용 오류 없이 실행됐지만, R-006/R-010/R-019/R-034의 요구사항 누락, R-011/R-038의 질문 무관 답변, R-033/R-035의 상품 필드 오류는 generation backlog로 유지한다. R-004는 이번에는 정확한 최소 부담금을 답해 strict useful로 전환됐고, R-008도 ISA 만기전환의 조건부 추가 한도를 분리해 수치 혼동을 해소했다.", ""])
    (ROOT / "docs/p27e_semantic_labeling.md").write_text(report, encoding="utf-8")

if __name__ == "__main__": main()
