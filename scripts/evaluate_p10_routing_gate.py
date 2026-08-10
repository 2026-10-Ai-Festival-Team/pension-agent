"""P10 experimental Router/Gate를 P9 gold cases로 offline 평가한다."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.multi_evidence import load_requirement_cases
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--gold", type=Path, default=ROOT / "evaluation/p9_control_gate_cases.json")
    parser.add_argument("--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p10_routing_gate_evaluation.json")
    args = parser.parse_args()
    questions = {item.question_id: item for item in load_questions(args.questions)}
    gold = json.loads(args.gold.read_text(encoding="utf-8"))["cases"]
    requirements = {item.question_id: item for item in load_requirement_cases(args.requirements)}
    router, gate, analyzer = ExperimentalRouter(), ExperimentalRouteGate(), QueryAnalyzer()
    retriever = build_frozen_retriever(args.corpus, args.index)
    rows = []
    for item in gold:
        question = questions[item["question_id"]]
        analysis = analyzer.analyze(question.question)
        results = retriever.search(question.question, top_k=10).results
        route = router.classify(analysis)
        decision = gate.assess(route.route, analysis, results, requirements.get(question.question_id))
        direct_hit = bool(question.direct_evidence_ids & {result.chunk_id for result in results}) if question.answerable else False
        rows.append({
            "question_id": question.question_id, "gold_route": item["gold_route"], "route": route.route,
            "route_reasons": route.reasons, "route_correct": route.route == item["gold_route"],
            "retrieval_direct_evidence_sufficient": direct_hit, "gate_pass": decision.sufficient,
            "gate_reason": decision.reason, "missing_slots": decision.missing_slots,
            "selected_chunk_ids": decision.selected_chunk_ids,
        })
    summary = {
        "case_count": len(rows),
        "routing_accuracy": round(sum(row["route_correct"] for row in rows) / len(rows), 3),
        "routing_misclassification_count": sum(not row["route_correct"] for row in rows),
        "false_rejection_count": sum(row["retrieval_direct_evidence_sufficient"] and not row["gate_pass"] and row["gold_route"] != "unsupported" for row in rows),
        "unsafe_pass_count": sum(not row["retrieval_direct_evidence_sufficient"] and row["gate_pass"] and row["gold_route"] != "unsupported" for row in rows),
        "gate_reasons": dict(Counter(row["gate_reason"] for row in rows)),
    }
    payload = {"experiment": "P10 experimental router and route-specific gate", "summary": summary, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
