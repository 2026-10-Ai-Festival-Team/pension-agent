"""P6-B requirement-specific retrieval을 HCX 호출 없이 비교한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.decomposed_retrieval import retrieve_by_requirement
from src.experiments.multi_evidence import RequirementEvidenceSelector, load_requirement_cases, selection_record
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--plans", type=Path, default=ROOT / "evaluation/p6_decomposed_retrieval_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p6_decomposed_retrieval_run.json")
    parser.add_argument("--per-query-top-k", type=int, default=5)
    args = parser.parse_args()

    requirement_cases = {case.question_id: case for case in load_requirement_cases(args.requirements)}
    plans = json.loads(args.plans.read_text(encoding="utf-8"))["cases"]
    questions = {item.question_id: item for item in load_questions(args.questions)}
    retriever = build_frozen_retriever(args.corpus, args.index)
    selector = RequirementEvidenceSelector()
    rows = []
    for plan in plans:
        question_id = plan["question_id"]
        question = questions[question_id]
        requirement_case = requirement_cases[question_id]
        existing = retriever.search(question.question, top_k=10).results
        decomposed = retrieve_by_requirement(retriever, plan["slot_queries"], args.per_query_top_k)
        existing_selection = selector.select(requirement_case, existing)
        decomposed_selection = selector.select(requirement_case, decomposed.merged_results)
        gold = question.direct_evidence_ids
        rows.append({
            "question_id": question_id,
            "question": question.question,
            "slot_queries": plan["slot_queries"],
            "existing": {**selection_record(existing_selection), "candidate_count": len(existing), "direct_gold_hit": bool({item.chunk_id for item in existing} & gold)},
            "decomposed": {
                **selection_record(decomposed_selection),
                "candidate_count": len(decomposed.merged_results),
                "direct_gold_hit": bool({item.chunk_id for item in decomposed.merged_results} & gold),
                "per_slot_chunk_ids": {slot: [item.chunk_id for item in results] for slot, results in decomposed.slot_results.items()},
            },
        })
    payload = {"experiment": "P6-B decomposed retrieval", "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "full_coverage_after": sum(row["decomposed"]["requirement_evidence_complete"] for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
