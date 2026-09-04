"""P17: P12/P15 계열 offline gate와 P16 Shadow E2E의 composition 차이를 진단한다.

HCX를 호출하지 않는다. P16의 실제 호출 기록은 읽기 전용으로 사용하고, 현재
``ConditionalRoutingShadowAgent.prepare``로 generation 전 상태만 재현한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.experiments.multi_evidence import load_requirement_cases, selection_record
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.generation.fake import FakeGenerator
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever


TARGET_IDS = ("R-002", "R-005", "R-006", "R-019", "R-027", "R-028")


def _load_jsonl(path: Path) -> dict[str, dict]:
    return {
        row["question_id"]: row
        for line in path.read_text(encoding="utf-8").splitlines()
        if (row := json.loads(line))
    }


def _slots(case) -> list[dict]:
    if case is None:
        return []
    return [
        {
            "name": slot.name,
            "key": slot.key,
            "terms": list(slot.terms),
            "min_matches": slot.min_matches,
            "retrieval_query": slot.retrieval_query,
        }
        for slot in case.slots
    ]


def _static_offline_snapshot(*, question: str, case, retriever, analyzer, router, gate) -> dict:
    """P12 full-40 evaluator의 static-case + original Top-10 composition을 재현한다."""
    analysis = analyzer.analyze(question)
    route = router.classify(analysis)
    base_results = tuple(retriever.search(analysis.question, top_k=10).results)
    decision = gate.assess(route.route, analysis, base_results, case)
    selection = gate.selector.select(case, base_results) if case is not None else None
    return {
        "route": route.route,
        "route_reasons": route.reasons,
        "requirement_case_source": "static_p12_registry" if case is not None else "none",
        "requirement_slots": _slots(case),
        "base_retrieved_chunk_ids": [item.chunk_id for item in base_results],
        "candidate_chunk_ids": [item.chunk_id for item in base_results],
        "selected_chunk_ids": decision.selected_chunk_ids,
        "slot_selection": selection_record(selection) if selection is not None else None,
        "evidence_sufficient": decision.sufficient,
        "gate_decision": decision.reason,
        "missing_slots": decision.missing_slots,
        "expected_hcx_call": decision.sufficient,
    }


def _shadow_snapshot(agent: ConditionalRoutingShadowAgent, question: str) -> dict:
    """P16 Agent와 같은 helper에서 만든 generation 전 state를 직렬화한다."""
    plan = agent.prepare(question, top_k=10)
    return {
        "route": plan.route.route,
        "route_reasons": plan.route.reasons,
        "requirement_case_source": "dynamic_requirement_builder" if plan.requirement_case is not None else "none",
        "requirement_slots": _slots(plan.requirement_case),
        "base_retrieved_chunk_ids": [item.chunk_id for item in plan.base_results],
        "candidate_chunk_ids": [item.chunk_id for item in plan.candidate_results],
        "selected_chunk_ids": plan.assessment.selected_chunk_ids,
        "merged_context_chunk_ids": [item.chunk_id for item in plan.contexts],
        "slot_selection": selection_record(plan.selection) if plan.selection is not None else None,
        "evidence_sufficient": plan.assessment.sufficient,
        "gate_decision": plan.assessment.reason,
        "missing_slots": plan.assessment.missing_requirements,
        "expected_hcx_call": plan.assessment.sufficient,
    }


def _owner(static: dict, shadow: dict) -> tuple[str, str]:
    if static["expected_hcx_call"] != shadow["expected_hcx_call"]:
        if static["requirement_case_source"] == "static_p12_registry" and shadow["requirement_case_source"] != "static_p12_registry":
            return "shadow_integration", "static case registry was not composed into the dynamic Shadow path"
        return "gate", "offline and Shadow gate decisions differ"
    if static["base_retrieved_chunk_ids"] != shadow["base_retrieved_chunk_ids"]:
        return "retrieval", "same frozen retriever returned a different original Top-10"
    return "none", "no pre-generation composition divergence detected"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--p12-requirements", type=Path, default=ROOT / "evaluation/p12_requirement_cases.json")
    parser.add_argument("--p16-shadow-run", type=Path, default=ROOT / "data/diagnostics/p16_shadow_hcx.json")
    parser.add_argument("--p16-shadow-review", type=Path, default=ROOT / "data/diagnostics/p16_shadow_reviewed.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p17_offline_e2e_divergence.json")
    args = parser.parse_args()

    questions = _load_jsonl(args.questions)
    static_cases = {case.question_id: case for case in load_requirement_cases(args.p12_requirements)}
    p16_rows = {row["question_id"]: row for row in json.loads(args.p16_shadow_run.read_text(encoding="utf-8"))["rows"]}
    review = _load_jsonl(args.p16_shadow_review)
    if not set(TARGET_IDS) <= set(questions) & set(p16_rows) & set(review):
        raise ValueError("P17 target rows are missing from the supplied artifacts")

    retriever = build_frozen_retriever(args.corpus, args.index)
    analyzer, router, gate = QueryAnalyzer(), ExperimentalRouter(), ExperimentalRouteGate()
    shadow_agent = ConditionalRoutingShadowAgent(
        retriever=retriever,
        generator=FakeGenerator(),
        analyzer=analyzer,
        router=router,
        gate=gate,
    )
    rows = []
    for question_id in TARGET_IDS:
        question = questions[question_id]["question"]
        static = _static_offline_snapshot(
            question=question,
            case=static_cases.get(question_id),
            retriever=retriever,
            analyzer=analyzer,
            router=router,
            gate=gate,
        )
        shadow = _shadow_snapshot(shadow_agent, question)
        actual = p16_rows[question_id]
        actual_context_ids = actual.get("retrieved_chunk_ids", [])
        replay_matches = (
            shadow["route"] == actual.get("route")
            and shadow["gate_decision"] == actual.get("evidence_reason")
            and shadow["expected_hcx_call"] == actual.get("generator_attempted")
            and shadow["merged_context_chunk_ids"] == actual_context_ids
        )
        owner, reason = _owner(static, shadow)
        reviewed = review[question_id]["review"]
        rows.append(
            {
                "question_id": question_id,
                "question": question,
                "p15_evaluation_coverage": "not_evaluated: P15 used H-001..H-020 and M-001..M-012, not R-series full-40 cases",
                "p12_static_offline": static,
                "p16_shadow_replay": shadow,
                "p16_recorded": {
                    "route": actual.get("route"),
                    "route_reasons": actual.get("route_reasons", []),
                    "retrieved_context_chunk_ids": actual_context_ids,
                    "evidence_sufficient": actual.get("evidence_sufficient"),
                    "gate_decision": actual.get("evidence_reason"),
                    "hcx_invoked": actual.get("generator_attempted"),
                    "hcx_accepted": actual.get("generator_called"),
                    "cited_chunk_ids": actual.get("cited_chunk_ids", []),
                    "failure_stage": actual.get("failure_stage"),
                },
                "p16_semantic_review": {
                    "factual_correctness": reviewed.get("factual_correctness"),
                    "requirement_coverage": reviewed.get("requirement_coverage"),
                    "grounding": reviewed.get("grounding"),
                    "hallucination": reviewed.get("hallucination"),
                    "information_limit_handling": reviewed.get("information_limit_handling"),
                },
                "recorded_shadow_replay_match": replay_matches,
                "retrieval_top10_matches": static["base_retrieved_chunk_ids"] == shadow["base_retrieved_chunk_ids"],
                "primary_owner": owner,
                "primary_reason": reason,
            }
        )

    payload = {
        "experiment": "P17 Offline-to-E2E Divergence Analysis",
        "hcx_called": False,
        "target_case_count": len(rows),
        "summary": {
            "p15_did_not_evaluate_target_r_cases": True,
            "p12_static_to_p16_dynamic_gate_decision_differences": sum(
                row["p12_static_offline"]["expected_hcx_call"] != row["p16_shadow_replay"]["expected_hcx_call"]
                for row in rows
            ),
            "recorded_shadow_replay_matches": sum(row["recorded_shadow_replay_match"] for row in rows),
            "frozen_retrieval_top10_matches": sum(row["retrieval_top10_matches"] for row in rows),
            "primary_owners": {
                owner: sum(row["primary_owner"] == owner for row in rows)
                for owner in sorted({row["primary_owner"] for row in rows})
            },
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
