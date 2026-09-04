"""P18: P16 Shadow와 동일한 preparation path로 Full-40을 offline 평가한다.

정적 question-ID requirement case를 gate 입력으로 사용하지 않는다. 이 스크립트의
중간 상태는 ``ConditionalRoutingShadowAgent.prepare``와 공용
``prepare_shadow_execution``을 모두 호출해 parity를 검증한다. HCX는 호출하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.experiments.shadow_execution import prepare_shadow_execution
from src.generation.fake import FakeGenerator
from src.orchestration.context_builder import ContextBuilder
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever


def _labels(path: Path) -> dict[str, dict]:
    return {item["question_id"]: item for item in json.loads(path.read_text(encoding="utf-8"))["labels"]}


def _questions(path: Path) -> dict[str, dict]:
    return {
        item["question_id"]: item
        for line in path.read_text(encoding="utf-8").splitlines()
        if (item := json.loads(line))
    }


def _plan_state(plan) -> dict:
    entities = plan.analysis.extracted_entities
    return {
        "route": plan.route.route,
        "route_reasons": plan.route.reasons,
        "extracted_entities": {
            "accounts": list(entities.accounts),
            "product_codes": list(entities.product_codes),
            "comparison": entities.comparison,
            "tax_intent": entities.tax_intent,
            "requested_fields": list(entities.requested_fields),
        },
        "requirement_plan": {
            "category": plan.route.requirement_case.question_id.removeprefix("dynamic:")
            if plan.requirement_case else None,
            "slots": [
                {
                    "name": slot.name,
                    "key": slot.key,
                    "terms": list(slot.terms),
                    "min_matches": slot.min_matches,
                    "retrieval_query": slot.retrieval_query,
                }
                for slot in (plan.requirement_case.slots if plan.requirement_case else ())
            ],
        },
        "base_retrieved_chunk_ids": [item.chunk_id for item in plan.base_results],
        "candidate_chunk_ids": [item.chunk_id for item in plan.candidate_results],
        "selected_merged_evidence_ids": [item.chunk_id for item in plan.contexts],
        "evidence_sufficient": plan.assessment.sufficient,
        "gate_decision": plan.assessment.reason,
        "missing_requirement_slots": plan.assessment.missing_requirements,
        "hcx_would_be_invoked": plan.assessment.sufficient,
    }


def _route_metrics(rows: list[dict]) -> dict:
    routes = ("simple", "compound", "unsupported")
    confusion = {gold: {predicted: 0 for predicted in routes} for gold in routes}
    for row in rows:
        confusion[row["gold_route"]][row["route"]] += 1
    accuracy = sum(row["route"] == row["gold_route"] for row in rows)
    return {
        "accuracy": f"{accuracy}/{len(rows)}",
        "compound_recall": f"{confusion['compound']['compound']}/{sum(confusion['compound'].values())}",
        "unsupported_recall": f"{confusion['unsupported']['unsupported']}/{sum(confusion['unsupported'].values())}",
        "confusion_matrix": confusion,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--labels", type=Path, default=ROOT / "evaluation/p11_full40_routing_labels.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p18_shared_shadow_preparation.json")
    args = parser.parse_args()

    questions, labels = _questions(args.questions), _labels(args.labels)
    if set(questions) != set(labels):
        raise ValueError("P18 questions and labels must match exactly")

    retriever = build_frozen_retriever(args.corpus, args.index)
    analyzer, router, gate, context_builder = QueryAnalyzer(), ExperimentalRouter(), ExperimentalRouteGate(), ContextBuilder()
    agent = ConditionalRoutingShadowAgent(
        retriever=retriever,
        generator=FakeGenerator(),
        analyzer=analyzer,
        router=router,
        gate=gate,
        context_builder=context_builder,
    )

    rows = []
    for question_id, question in questions.items():
        agent_plan = agent.prepare(question["question"], top_k=10)
        direct_plan = prepare_shadow_execution(
            question=question["question"],
            top_k=10,
            retriever=retriever,
            analyzer=analyzer,
            context_builder=context_builder,
            router=router,
            gate=gate,
            requirement_retrieval_top_k=agent.requirement_retrieval_top_k,
        )
        state, direct_state = _plan_state(agent_plan), _plan_state(direct_plan)
        label = labels[question_id]
        rows.append(
            {
                "question_id": question_id,
                "question": question["question"],
                "gold_route": label["gold_route"],
                "semantic_retrieval_sufficiency_reference": label["evidence_sufficiency"],
                **state,
                "shared_preparation_parity": state == direct_state,
                "parity_mismatch_fields": sorted(
                    key for key in set(state) | set(direct_state) if state.get(key) != direct_state.get(key)
                ),
            }
        )

    known = [row for row in rows if row["semantic_retrieval_sufficiency_reference"] in {"full", "partial", "none"}]
    answerable_known = [row for row in known if row["gold_route"] != "unsupported"]
    false_rejection = [row for row in answerable_known if row["semantic_retrieval_sufficiency_reference"] == "full" and not row["hcx_would_be_invoked"]]
    unsafe_pass = [row for row in answerable_known if row["semantic_retrieval_sufficiency_reference"] in {"partial", "none"} and row["hcx_would_be_invoked"]]
    compound = [row for row in rows if row["gold_route"] == "compound"]
    payload = {
        "experiment": "P18 Full-40 Shared Shadow Preparation Parity",
        "hcx_called": False,
        "static_question_id_cases_used_for_preparation": False,
        "summary": {
            "cases": len(rows),
            "shared_preparation_parity": f"{sum(row['shared_preparation_parity'] for row in rows)}/{len(rows)}",
            "routing": _route_metrics(rows),
            "compound_with_dynamic_requirement_plan": f"{sum(bool(row['requirement_plan']['slots']) for row in compound)}/{len(compound)}",
            "known_false_rejection": {"count": len(false_rejection), "question_ids": [row["question_id"] for row in false_rejection]},
            "known_unsafe_pass": {"count": len(unsafe_pass), "question_ids": [row["question_id"] for row in unsafe_pass]},
            "gate_decisions": dict(Counter(row["gate_decision"] for row in rows)),
            "hcx_would_be_invoked": sum(row["hcx_would_be_invoked"] for row in rows),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
