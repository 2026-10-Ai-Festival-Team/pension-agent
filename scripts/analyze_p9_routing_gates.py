"""P9: router, evidence gate, selection, and schema failure ownership 진단."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestration.context_builder import ContextBuilder
from src.orchestration.evidence_assessor import EvidenceAssessor
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def current_route(analysis) -> str:
    if analysis.intent in {"unsupported_or_personal", "conditional_recommendation"}:
        return "unsupported"
    return "compound" if analysis.requires_comparison else "simple"


def p8b_outcomes(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["question_id"]].append({
            "representation": row.get("representation"), "status": row.get("status"),
            "citation_validation_pass": row.get("citation_validation_pass"),
            "semantic_correctness": row.get("semantic_correctness"),
            "generation_error": row.get("generation_error"),
        })
    return dict(grouped)


def owner_for(row):
    question_id = row["question_id"]
    if question_id == "R-001":
        return "generation_schema", "same structured-output failure in A/B; representation-independent"
    if question_id == "R-004":
        return "selection", "requirement-specific selection chose evidence that cannot answer the minimum contribution question"
    if question_id == "R-009":
        return "router", "simple tax fact was incorrectly evaluated by experimental compound completeness gate"
    if question_id in {"R-024", "R-010"}:
        return "retrieval", "required evidence is incomplete; pre-generation rejection is appropriate"
    if row["gold_route"] == "compound" and row["current_route"] == "simple":
        return "router", "current QueryAnalyzer does not expose all independent requirements"
    if row["gate_state"] == "retrieval_insufficient_gate_pass":
        return "gate", "current EvidenceAssessor treats any non-empty context as sufficient"
    if row["gold_route"] == "unsupported":
        return "none", "unsupported/personal policy correctly rejects before generation"
    return "none", "no P9 primary failure observed in the diagnostic subset"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/p9_control_gate_cases.json")
    parser.add_argument("--p8b-run", type=Path, default=ROOT / "data/diagnostics/p8b_compound_citation_stability_reviewed.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p9_routing_gate_analysis.json")
    args = parser.parse_args()
    questions = {item.question_id: item for item in load_questions(args.questions)}
    cases = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    outcomes = p8b_outcomes(args.p8b_run)
    retriever = build_frozen_retriever(args.corpus, args.index)
    analyzer, builder, assessor = QueryAnalyzer(), ContextBuilder(), EvidenceAssessor()
    rows = []
    for item in cases:
        question = questions[item["question_id"]]
        analysis = analyzer.analyze(question.question)
        search = retriever.search(analysis.question, top_k=10)
        contexts = builder.build(search.results, 5)
        assessment = assessor.assess(analysis, contexts)
        retrieved_ids = {result.chunk_id for result in search.results}
        context_ids = {result.chunk_id for result in contexts}
        direct_ids = question.direct_evidence_ids
        retrieval_sufficient = bool(direct_ids & retrieved_ids) if question.answerable else False
        context_sufficient = bool(direct_ids & context_ids) if question.answerable else False
        gate_state = (
            "retrieval_sufficient_gate_pass" if retrieval_sufficient and assessment.sufficient else
            "retrieval_sufficient_gate_reject" if retrieval_sufficient else
            "retrieval_insufficient_gate_pass" if assessment.sufficient else
            "retrieval_insufficient_gate_reject"
        )
        row = {
            "question_id": question.question_id, "question": question.question, "gold_route": item["gold_route"],
            "current_route": current_route(analysis), "current_intent": analysis.intent,
            "current_entities": analysis.entities, "requires_comparison": analysis.requires_comparison,
            "retrieval_direct_evidence_sufficient": retrieval_sufficient,
            "selected_context_direct_evidence_sufficient": context_sufficient,
            "gate_pass": assessment.sufficient, "gate_reason": assessment.reason, "gate_state": gate_state,
            "retrieved_chunk_ids": [result.chunk_id for result in search.results],
            "selected_context_chunk_ids": [result.chunk_id for result in contexts],
            "p8b_outcomes": outcomes.get(question.question_id, []), "notes": item["notes"],
        }
        owner, root_cause = owner_for(row)
        row.update({"primary_owner": owner, "root_cause": root_cause})
        rows.append(row)
    summary = {
        "case_count": len(rows),
        "routing_accuracy": round(sum(row["gold_route"] == row["current_route"] for row in rows) / len(rows), 3),
        "routing_misclassification_count": sum(row["gold_route"] != row["current_route"] for row in rows),
        "gate_states": dict(Counter(row["gate_state"] for row in rows)),
        "primary_owners": dict(Counter(row["primary_owner"] for row in rows)),
        "false_rejection_count": sum(row["gate_state"] == "retrieval_sufficient_gate_reject" for row in rows),
        "unsafe_pass_count": sum(row["gate_state"] == "retrieval_insufficient_gate_pass" and row["gold_route"] != "unsupported" for row in rows),
    }
    payload = {"experiment": "P9 routing and gate failure analysis", "summary": summary, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
