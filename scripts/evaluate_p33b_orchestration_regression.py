"""P33-B generalized orchestration/policy offline regression.

This script intentionally never calls HCX.  P32 and P33 are development
regression sets after their failure-attribution stages; the output proves only
that the deterministic candidate path behaves as specified before a future,
new P34 holdout is created.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_p32b_orchestration_regression import _state
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _p33_expected(row: dict, state: dict) -> bool:
    behavior = row["expected_policy_behavior"]
    if behavior in {"clarify_before_recommendation", "clarify_or_limit"}:
        return state["policy_action"] == "clarify"
    if behavior == "comparison_not_single_recommendation":
        return state["policy_action"] == "comparison"
    if behavior == "safe_block":
        return state["policy_action"] == "safe_block"
    return state["evidence_sufficient"] and state["generator_would_be_called"]


def _first_turn_policy_check(agent: P27DStructuredOutputAgent, row: dict) -> dict:
    """Check only policy rows through the public candidate ``answer`` path.

    FakeGenerator is never reached by these rows.  This makes sure that a
    clarification or a safe block includes the necessary first-turn wording,
    rather than merely recording an internal policy route.
    """
    response = agent.answer(row["question"], top_k=10)
    trace = response["think_trace"]
    answer = response["answer"]
    expected = row["expected_policy_behavior"]
    required_terms: tuple[str, ...]
    if row["question_id"] == "P33-016":
        required_terms = ("위험 성향", "운용 목적")
    elif row["question_id"] == "P33-019":
        required_terms = ("계좌 유형", "수령기간", "소득")
    elif row["question_id"] == "P33-018":
        required_terms = ("손실", "주식형")
    elif expected == "comparison_not_single_recommendation":
        required_terms = ("후보 상품", "단정")
    elif expected == "safe_block":
        required_terms = {
            "P33-020": ("개인 식별정보",),
            "P33-021": ("미래 시장",),
            "P33-022": ("내부 지시",),
        }[row["question_id"]]
    else:
        required_terms = ()
    return {
        "question_id": row["question_id"],
        "assessment_reason": trace["assessment_reason"],
        "generator_called": trace["generator_called"],
        "required_terms": list(required_terms),
        "required_terms_present": all(term in answer for term in required_terms),
    }


def _question_bank_fixture(agent: P27DStructuredOutputAgent, row: dict) -> dict:
    expected = row["fixtures"]["gate_policy"]["expected_behavior"][0]
    fixture_valid = (
        row["planner_slot_status"] == "needs_annotation"
        and row["fixtures"]["planner"]["status"] == "needs_annotation"
        and bool(row["fixtures"]["gate_policy"]["expected_behavior"])
    )
    if expected not in {"clarify", "abstain"}:
        return {
            "id": row["id"],
            "expected": expected,
            "fixture_valid": fixture_valid,
            "policy_checked": False,
            "pass": fixture_valid,
        }

    state = _state(agent, row["question"])
    expected_action = "clarify" if expected == "clarify" else "safe_block"
    return {
        "id": row["id"],
        "expected": expected,
        "fixture_valid": fixture_valid,
        "policy_checked": True,
        "state": state,
        "pass": fixture_valid and state["policy_action"] == expected_action,
    }


def _report(payload: dict) -> str:
    p33 = payload["p33"]
    bank = payload["question_bank_v1"]
    lines = [
        "# P33-B: Generalized Orchestration / Policy Offline Regression",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음. 이 결과는 semantic score나 일반화 성능을 주장하지 않는다.",
        "- P32·P33은 failure attribution 이후 개발 회귀셋으로만 사용한다.",
        "- Corpus, BM25 파라미터, HCX prompt/schema, citation validator, provider pacing은 변경하지 않았다.",
        "",
        "## Results",
        "",
        f"- P15 route/gate regressions: **{payload['p32b_reference']['p15_regression_count']}**",
        f"- P31 previously-sufficient preparation regressions: **{payload['p32b_reference']['p31_regression_count']}**",
        f"- P32 deterministic regression: **{payload['p32b_reference']['p32_expected_behavior_pass']}**",
        f"- P33 deterministic expected behavior: **{p33['pass_count']}/{p33['total']}**",
        f"- P33 manifest-source overlap: **{p33['source_relevance_pass_count']}/{p33['source_relevance_total']}**",
        f"- P33 first-turn policy wording: **{p33['first_turn_policy_pass_count']}/{p33['first_turn_policy_total']}**",
        f"- Question bank fixture validity: **{bank['fixture_valid_count']}/{bank['total']}**",
        f"- Question bank clarify/abstain policy fixtures: **{bank['policy_pass_count']}/{bank['policy_checked_count']}**",
        "",
        "## Source-relevance diagnostic",
        "",
        "The following P33 development cases did not contain a manifest-declared acceptable chunk in the selected context:",
        "",
    ]
    if p33["source_relevance_mismatches"]:
        lines.extend(f"- `{question_id}`" for question_id in p33["source_relevance_mismatches"])
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "The candidate now uses structural requirement plans (comparison axes, procedure/condition/benefit, account-specific tax and product-field boundaries) and policy predicates (clarify, personal account, external prediction, prompt injection). No question-ID branch was introduced.",
        "",
        "`manifest-source overlap` is an exact check against P33's declared acceptable chunk IDs; it is stricter than later human semantic-equivalence adjudication. A mismatch is retained as a retrieval/selection regression candidate, not silently counted as a pass.",
        "",
        "P33-B is an offline regression gate only. A new, non-overlapping P34 manifest may be frozen only after the declared source-relevance regression gate is resolved or adjudicated.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--p32b", type=Path, default=ROOT / "evaluation/p32b_orchestration_regression.json")
    parser.add_argument("--p33-manifest", type=Path, default=ROOT / "evaluation/p33_holdout_manifest.json")
    parser.add_argument("--question-bank", type=Path, default=ROOT / "evaluation/question_bank_v1.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p33b_orchestration_regression.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p33b_generalized_orchestration_fix.md")
    args = parser.parse_args()

    agent = P27DStructuredOutputAgent(
        build_frozen_retriever(args.corpus, args.index),
        FakeGenerator(),
    )
    p32b = json.loads(args.p32b.read_text(encoding="utf-8"))
    manifest = json.loads(args.p33_manifest.read_text(encoding="utf-8"))

    p33_rows = []
    policy_rows = []
    for row in manifest["questions"]:
        state = _state(agent, row["question"])
        passed = _p33_expected(row, state)
        expected_source_ids = set(row["acceptable_equivalent_evidence"])
        selected_source_ids = set(state.get("selected_chunk_ids", []))
        source_relevance_pass = not expected_source_ids or bool(expected_source_ids & selected_source_ids)
        p33_rows.append({
            "question_id": row["question_id"],
            "answerability": row["answerability"],
            "expected_policy_behavior": row["expected_policy_behavior"],
            "state": state,
            "pass": passed,
            "declared_acceptable_chunk_ids": sorted(expected_source_ids),
            "selected_chunk_ids": sorted(selected_source_ids),
            "source_relevance_pass": source_relevance_pass,
        })
        if row["expected_policy_behavior"] in {
            "clarify_before_recommendation", "clarify_or_limit",
            "comparison_not_single_recommendation", "safe_block",
        }:
            policy_rows.append(_first_turn_policy_check(agent, row))

    bank_rows = [_question_bank_fixture(agent, row) for row in _jsonl(args.question_bank)]
    checked_bank = [row for row in bank_rows if row["policy_checked"]]
    payload = {
        "experiment": "P33-B generalized orchestration and policy offline regression",
        "hcx_called": False,
        "p32b_reference": {
            "p15_regression_count": len(p32b["p15_regressions"]),
            "p31_regression_count": len(p32b["p31_regressions"]),
            "p32_expected_behavior_pass": p32b["p32_expected_behavior_pass"],
        },
        "p33": {
            "total": len(p33_rows),
            "pass_count": sum(row["pass"] for row in p33_rows),
            "rows": p33_rows,
            "source_relevance_total": sum(bool(row["declared_acceptable_chunk_ids"]) for row in p33_rows),
            "source_relevance_pass_count": sum(
                row["source_relevance_pass"] for row in p33_rows if row["declared_acceptable_chunk_ids"]
            ),
            "source_relevance_mismatches": [
                row["question_id"] for row in p33_rows
                if row["declared_acceptable_chunk_ids"] and not row["source_relevance_pass"]
            ],
            "first_turn_policy_total": len(policy_rows),
            "first_turn_policy_pass_count": sum(
                not row["generator_called"] and row["required_terms_present"] for row in policy_rows
            ),
            "first_turn_policy_rows": policy_rows,
        },
        "question_bank_v1": {
            "total": len(bank_rows),
            "fixture_valid_count": sum(row["fixture_valid"] for row in bank_rows),
            "policy_checked_count": len(checked_bank),
            "policy_pass_count": sum(row["pass"] for row in checked_bank),
            "expected_behavior_counts": dict(Counter(row["expected"] for row in bank_rows)),
            "rows": bank_rows,
        },
    }
    payload["go_for_new_holdout_only"] = (
        payload["p32b_reference"]["p15_regression_count"] == 0
        and payload["p32b_reference"]["p31_regression_count"] == 0
        and payload["p33"]["pass_count"] == payload["p33"]["total"]
        and payload["p33"]["source_relevance_pass_count"] == payload["p33"]["source_relevance_total"]
        and payload["p33"]["first_turn_policy_pass_count"] == payload["p33"]["first_turn_policy_total"]
        and payload["question_bank_v1"]["fixture_valid_count"] == payload["question_bank_v1"]["total"]
        and payload["question_bank_v1"]["policy_pass_count"] == payload["question_bank_v1"]["policy_checked_count"]
    )
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({
        "p33": f"{payload['p33']['pass_count']}/{payload['p33']['total']}",
        "p33_first_turn_policy": f"{payload['p33']['first_turn_policy_pass_count']}/{payload['p33']['first_turn_policy_total']}",
        "p33_manifest_source_overlap": f"{payload['p33']['source_relevance_pass_count']}/{payload['p33']['source_relevance_total']}",
        "question_bank_policy": f"{payload['question_bank_v1']['policy_pass_count']}/{payload['question_bank_v1']['policy_checked_count']}",
        "go_for_new_holdout_only": payload["go_for_new_holdout_only"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
