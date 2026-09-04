"""P32-B deterministic orchestration 회귀 검증.

HCX를 호출하지 않는다. P32는 이미 개발셋이므로 이 실행은 일반화 성능이 아니라
planner/matcher/policy 수정이 실제 shared candidate preparation에 반영되는지와
P15/P31의 gate 회귀가 없는지를 확인한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _state(agent: P27DStructuredOutputAgent, question: str) -> dict:
    analysis = agent.analyzer.analyze(question)
    support = agent.router.support_classifier.classify(analysis.question)
    if not support.supported and (
        support.category
        in {
            "personal_account_lookup",
            "unavailable_external_information",
            "prompt_injection",
        }
        or support.reason == "external_prediction_requested"
    ):
        category = (
            "unavailable_external_information"
            if support.reason == "external_prediction_requested"
            else support.category
        )
        return {
            "route": "unsupported",
            "category": category,
            "slot_keys": [],
            "evidence_sufficient": False,
            "reason": category,
            "generator_would_be_called": False,
            "policy_action": "safe_block",
        }
    recommendation = agent.financial_policy.recommendation_decision(analysis)
    if recommendation.is_recommendation_context:
        return {
            "route": "policy",
            "category": None,
            "slot_keys": [],
            "evidence_sufficient": False,
            "reason": "recommendation_comparison_only" if recommendation.profile_complete else "conditional_recommendation_requires_user_conditions",
            "generator_would_be_called": False,
            "policy_action": "comparison" if recommendation.profile_complete else "clarify",
        }
    if agent.financial_policy.requires_personal_tax_clarification(analysis):
        return {
            "route": "policy",
            "category": None,
            "slot_keys": [],
            "evidence_sufficient": False,
            "reason": "personal_tax_conditions_required",
            "generator_would_be_called": False,
            "policy_action": "clarify",
        }
    plan = agent.prepare(question, top_k=10)
    case = plan.requirement_case
    return {
        "route": plan.route.route,
        "category": case.question_id.removeprefix("dynamic:") if case else None,
        "slot_keys": [slot.key for slot in case.slots] if case else [],
        "evidence_sufficient": plan.assessment.sufficient,
        "reason": plan.assessment.reason,
        "missing_slots": list(plan.assessment.missing_requirements),
        "selected_chunk_ids": [item.chunk_id for item in plan.contexts],
        "generator_would_be_called": plan.assessment.sufficient,
        "policy_action": None,
    }


def _expected_p32_ok(row: dict, state: dict) -> bool:
    behavior = row["expected_policy_behavior"]
    if behavior in {"clarify_before_recommendation", "clarify_or_limit"}:
        return state["policy_action"] == "clarify"
    if behavior == "comparison_not_single_recommendation":
        return state["policy_action"] == "comparison"
    if row["answerability"] == "unsupported":
        return state["route"] == "unsupported" and not state["generator_would_be_called"]
    return state["evidence_sufficient"]


def _report(payload: dict) -> str:
    lines = [
        "# P32-B: Generalized Orchestration Offline Regression",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음",
        "- P32는 P32-A attribution 이후 개발 회귀셋으로만 사용",
        "- Corpus, BM25 파라미터, citation validator, provider pacing은 변경하지 않음",
        "",
        "## Results",
        "",
        f"- P15 route/gate regressions: **{len(payload['p15_regressions'])}**",
        f"- P31 previously-sufficient preparation regressions: **{len(payload['p31_regressions'])}**",
        f"- P32 expected deterministic behavior: **{payload['p32_expected_behavior_pass']}**",
        "",
        "## P32 failed-case owners after generalized preparation",
        "",
        "| ID | Route | Requirement category | Gate/policy result |",
        "|---|---|---|---|",
    ]
    for row in payload["p32_previously_failed"]:
        lines.append(
            f"| {row['question_id']} | {row['state']['route']} | {row['state']['category'] or '-'} | {row['state']['reason']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This report verifies deterministic preparation behavior only. It does not relabel answers, call HCX, or establish P32 as a generalized quality score. Any P32 improvement must be validated on a new frozen P33 holdout.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--p15-questions", type=Path, default=ROOT / "evaluation/p15_mini_holdout_questions.json")
    parser.add_argument("--p15-labels", type=Path, default=ROOT / "evaluation/p15_mini_holdout_labels.json")
    parser.add_argument("--p31-execution", type=Path, default=ROOT / "evaluation/p31_candidate_execution.jsonl")
    parser.add_argument("--p32-manifest", type=Path, default=ROOT / "evaluation/p32_holdout_manifest.json")
    parser.add_argument("--p32-labels", type=Path, default=ROOT / "evaluation/p32_semantic_labels.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p32b_orchestration_regression.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p32b_generalized_orchestration_fix.md")
    args = parser.parse_args()

    agent = P27DStructuredOutputAgent(
        build_frozen_retriever(args.corpus, args.index),
        FakeGenerator(),
    )

    p15_labels = {row["question_id"]: row for row in json.loads(args.p15_labels.read_text(encoding="utf-8"))["labels"]}
    p15_rows = []
    for row in json.loads(args.p15_questions.read_text(encoding="utf-8"))["questions"]:
        state = _state(agent, row["question"])
        expected = p15_labels[row["question_id"]]
        p15_rows.append({"question_id": row["question_id"], "state": state, "expected": expected})
    p15_regressions = [
        row["question_id"] for row in p15_rows
        # P29 이후 one-turn clarification은 기존 holdout의 ``unsupported``
        # 안전 차단과 동등하게 상품 추천을 막는다. 생성기를 호출하지 않고
        # 필요한 조건을 첫 응답에 요구하므로 route 문자열 차이만으로 회귀로
        # 계산하지 않는다.
        if (row["state"]["route"] != row["expected"]["gold_route"] and row["state"]["policy_action"] is None)
        or (row["state"]["evidence_sufficient"] != row["expected"]["evidence_sufficient_expected"] and row["state"]["policy_action"] is None)
    ]

    p31_rows = _jsonl(args.p31_execution)
    p31_regressions = []
    for row in p31_rows:
        state = _state(agent, row["question"])
        if row["evidence_sufficient"] and not state["evidence_sufficient"] and state["policy_action"] is None:
            p31_regressions.append({"question_id": row["question_id"], "before_reason": row["evidence_reason"], "after": state})

    manifest = json.loads(args.p32_manifest.read_text(encoding="utf-8"))
    labels = {row["question_id"]: row for row in json.loads(args.p32_labels.read_text(encoding="utf-8"))["labels"]}
    p32_rows = []
    for row in manifest["questions"]:
        state = _state(agent, row["question"])
        p32_rows.append({
            "question_id": row["question_id"],
            "answerability": row["answerability"],
            "expected_policy_behavior": row["expected_policy_behavior"],
            "previous_strict_useful": labels[row["question_id"]]["strict_useful"],
            "state": state,
            "expected_deterministic_behavior_pass": _expected_p32_ok(row, state),
        })
    p32_failed = [row for row in p32_rows if not row["previous_strict_useful"]]
    p32_expected_pass = f"{sum(row['expected_deterministic_behavior_pass'] for row in p32_rows)}/{len(p32_rows)}"

    payload = {
        "experiment": "P32-B generalized orchestration offline regression",
        "hcx_called": False,
        "p15_regressions": p15_regressions,
        "p31_regressions": p31_regressions,
        "p32_expected_behavior_pass": p32_expected_pass,
        "p32_rows": p32_rows,
        "p32_previously_failed": p32_failed,
        "go_for_new_holdout_only": not p15_regressions and not p31_regressions,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({
        "p15_regressions": p15_regressions,
        "p31_regressions": [row["question_id"] for row in p31_regressions],
        "p32_expected_behavior_pass": p32_expected_pass,
        "go_for_new_holdout_only": payload["go_for_new_holdout_only"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
