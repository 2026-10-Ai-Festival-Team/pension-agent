"""P30: dynamic requirement coverage와 상품 field 경계를 HCX 없이 검증한다.

P27-E single-pass production candidate는 바꾸지 않는다. 이 스크립트는
candidate preparation이 실제 Shadow와 동일한 공용 ``prepare`` 경로를 사용해
planner miss와 field confusion을 줄이는지만 기록한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.experiments.shadow_execution import prepare_shadow_execution
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


TARGET_REQUIREMENTS = {
    "R-011": (
        "retirement_income_transfer_tax_deferral",
        "retirement_income_annuity_tax_timing",
    ),
    "R-019": ("dc_withdrawal_eligibility", "dc_withdrawal_legal_grounds"),
    "R-035": ("KR5113420012:investment_risk", "KR5113420012:principal_loss_possible"),
    "R-038": ("early_withdrawal_eligibility", "early_withdrawal_legal_grounds"),
}
FIELD_TARGET = "R-034"
P24B_SUFFICIENT = {"R-010", "R-024", "R-028", "R-037"}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _plan_state(plan) -> dict:
    case = plan.requirement_case
    return {
        "route": plan.route.route,
        "category": case.question_id.removeprefix("dynamic:") if case else None,
        "slot_keys": [slot.key for slot in case.slots] if case else [],
        "selected_chunk_ids": [item.chunk_id for item in plan.contexts],
        "candidate_chunk_ids": [item.chunk_id for item in plan.candidate_results],
        "evidence_sufficient": plan.assessment.sufficient,
        "gate_decision": plan.assessment.reason,
        "missing_slots": list(plan.assessment.missing_requirements),
    }


def _shared_plan(agent: P26CandidateAgent, question: str):
    return prepare_shadow_execution(
        question=question,
        top_k=10,
        retriever=agent.retriever,
        analyzer=agent.analyzer,
        context_builder=agent.context_builder,
        router=agent.router,
        gate=agent.gate,
        requirement_retrieval_top_k=agent.requirement_retrieval_top_k,
    )


def _report(payload: dict) -> str:
    lines = [
        "# P30: Requirement Planner & Product Field Boundary",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음; corpus, BM25 파라미터, prompt, citation validator는 변경하지 않음",
        "- 기존 shared preparation 경로에서 requirement plan과 slot matcher만 검증",
        "- 총보수·기타비용·투자 비용 예시를 서로 대체하지 않는 canonical field로 분리",
        "",
        "## Planner target cases",
        "",
        "| ID | Expected slots | Generated slots | Gate | Contexts |",
        "|---|---|---|---|---:|",
    ]
    for row in payload["planner_targets"]:
        lines.append(
            f"| {row['question_id']} | {', '.join(row['expected_slot_keys'])} | "
            f"{', '.join(row['generated_slot_keys'])} | "
            f"{'pass' if row['evidence_sufficient'] else 'reject'} | {len(row['selected_chunk_ids'])} |"
        )
    field = payload["field_target"]
    lines.extend(
        [
            "",
            "## Product field boundary",
            "",
            f"- {field['question_id']} generated fields: {', '.join(field['generated_slot_keys'])}",
            "- `total_fee`, `other_expenses`, `example_cost`는 각각 별도 slot이며, 비용 예시만으로 총보수 slot을 충족하지 않는다.",
            "",
            "## Offline regression",
            "",
            f"- Shared preparation parity: {payload['shared_preparation_parity']}",
            f"- P15 mini-holdout route/gate regressions: {', '.join(payload['p15_route_gate_regressions']) or '0'}",
            f"- Known false rejection: {', '.join(payload['known_false_rejection']) or '0'}",
            f"- Known unsafe pass: {', '.join(payload['known_unsafe_pass']) or '0'}",
            f"- Mean selected context count: {payload['mean_selected_contexts']}",
            "",
            "## Decision",
            "",
            "Go only for offline candidate validation when all target plans, shared-path parity, and P15 route/gate checks pass. Semantic answer quality requires a separate, controlled HCX evaluation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--p15-questions", type=Path, default=ROOT / "evaluation/p15_mini_holdout_questions.json")
    parser.add_argument("--p15-labels", type=Path, default=ROOT / "evaluation/p15_mini_holdout_labels.json")
    parser.add_argument("--reference", type=Path, default=ROOT / "data/diagnostics/p24b_full40_shared_preparation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p30_requirement_boundary_offline.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p30_requirement_planner_product_field_boundary.md")
    args = parser.parse_args()

    questions = _jsonl(args.questions)
    reference = {row["question_id"]: row for row in json.loads(args.reference.read_text(encoding="utf-8"))["rows"]}
    agent = P26CandidateAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    states: dict[str, dict] = {}
    parity_failures: list[str] = []
    for row in questions:
        candidate = agent.prepare(row["question"], top_k=10)
        shared = _shared_plan(agent, row["question"])
        state, shared_state = _plan_state(candidate), _plan_state(shared)
        states[row["question_id"]] = state
        if state != shared_state:
            parity_failures.append(row["question_id"])

    planner_targets = [
        {
            "question_id": question_id,
            "expected_slot_keys": list(expected),
            "generated_slot_keys": states[question_id]["slot_keys"],
            "evidence_sufficient": states[question_id]["evidence_sufficient"],
            "selected_chunk_ids": states[question_id]["selected_chunk_ids"],
        }
        for question_id, expected in TARGET_REQUIREMENTS.items()
    ]
    target_plan_failures = [
        row["question_id"]
        for row in planner_targets
        if tuple(row["generated_slot_keys"]) != tuple(row["expected_slot_keys"])
    ]
    field_target = {
        "question_id": FIELD_TARGET,
        "generated_slot_keys": states[FIELD_TARGET]["slot_keys"],
        "evidence_sufficient": states[FIELD_TARGET]["evidence_sufficient"],
        "selected_chunk_ids": states[FIELD_TARGET]["selected_chunk_ids"],
    }
    expected_fields = ("KR5110501016:total_fee", "KR5110501016:investment_target")
    field_boundary_ok = tuple(field_target["generated_slot_keys"]) == expected_fields

    labels = {row["question_id"]: row for row in json.loads(args.p15_labels.read_text(encoding="utf-8"))["labels"]}
    p15_regressions: list[str] = []
    for row in json.loads(args.p15_questions.read_text(encoding="utf-8"))["questions"]:
        state = _plan_state(agent.prepare(row["question"], top_k=10))
        expected = labels[row["question_id"]]
        if (state["route"], state["evidence_sufficient"]) != (
            expected["gold_route"], expected["evidence_sufficient_expected"],
        ):
            p15_regressions.append(row["question_id"])

    known_false_rejection = [
        question_id for question_id, state in states.items()
        if reference[question_id]["semantic_retrieval_sufficiency_reference"] == "full"
        and not state["evidence_sufficient"]
    ]
    known_unsafe_pass = [
        question_id for question_id, state in states.items()
        if reference[question_id]["semantic_retrieval_sufficiency_reference"] in {"partial", "none"}
        and question_id not in P24B_SUFFICIENT and state["evidence_sufficient"]
    ]
    payload = {
        "experiment": "P30 requirement planner and product field boundary",
        "hcx_called": False,
        "production_agent_changed": False,
        "shared_preparation_parity": f"{len(states) - len(parity_failures)}/{len(states)}",
        "shared_preparation_parity_failures": parity_failures,
        "planner_targets": planner_targets,
        "planner_target_failures": target_plan_failures,
        "field_target": field_target,
        "field_boundary_ok": field_boundary_ok,
        "p15_route_gate_regressions": p15_regressions,
        "known_false_rejection": known_false_rejection,
        "known_unsafe_pass": known_unsafe_pass,
        "mean_selected_contexts": round(sum(len(state["selected_chunk_ids"]) for state in states.values()) / len(states), 2),
        "go": not (
            parity_failures or target_plan_failures or not field_boundary_ok or p15_regressions
            or known_false_rejection or known_unsafe_pass
        ),
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("shared_preparation_parity", "planner_target_failures", "field_boundary_ok", "p15_route_gate_regressions", "known_false_rejection", "known_unsafe_pass", "go")}, ensure_ascii=False, indent=2))
    if not payload["go"]:
        raise SystemExit("P30 offline validation failed; HCX evaluation is blocked")


if __name__ == "__main__":
    main()
