"""P26 candidate path를 HCX 호출 전 Full-40/P15에서 고정 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever

P24B_CURRENTLY_SUFFICIENT = {"R-010", "R-024", "R-028", "R-037"}
PARITY_FIELDS = (
    "route",
    "extracted_entities",
    "requirement_plan",
    "base_retrieved_chunk_ids",
    "candidate_chunk_ids",
    "selected_merged_evidence_ids",
    "evidence_sufficient",
    "gate_decision",
    "missing_requirement_slots",
    "hcx_would_be_invoked",
)


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _state(agent: P26CandidateAgent, question: str) -> dict:
    plan = agent.prepare(question, top_k=10)
    entities = plan.analysis.extracted_entities
    return {
        "route": plan.route.route,
        "extracted_entities": {
            "accounts": list(entities.accounts),
            "product_codes": list(entities.product_codes),
            "comparison": entities.comparison,
            "tax_intent": entities.tax_intent,
            "requested_fields": list(entities.requested_fields),
        },
        "requirement_plan": {
            "category": plan.route.requirement_case.question_id.removeprefix("dynamic:")
            if plan.route.requirement_case
            else None,
            "slots": [
                {
                    "name": slot.name,
                    "key": slot.key,
                    "terms": list(slot.terms),
                    "min_matches": slot.min_matches,
                    "retrieval_query": slot.retrieval_query,
                }
                for slot in (plan.route.requirement_case.slots if plan.route.requirement_case else ())
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


def _markdown(payload: dict) -> str:
    targets = payload["target_cases"]
    lines = [
        "# P26 Candidate: Offline Preflight",
        "",
        "P24-B requirement retrieval/matcher를 운영 기본 Agent가 아닌 P26 candidate evaluation path에만 연결해 검증했다. HCX는 호출하지 않았다.",
        "",
        "## Full-40 parity",
        "",
        f"- P24-B 기준 preparation parity: {payload['full40_preparation_parity']}",
        f"- known false rejection: {payload['known_false_rejection']}",
        f"- known unsafe pass: {payload['known_unsafe_pass']}",
        f"- P15 mini-holdout route/gate regression: {payload['p15_route_gate_regressions']}",
        "",
        "## P24-B 대상",
        "",
        "| ID | gate | missing slots | selected evidence |",
        "|---|---|---|---|",
    ]
    for row in targets:
        lines.append(
            f"| {row['question_id']} | {'pass' if row['evidence_sufficient'] else 'reject'} | "
            f"{', '.join(row['missing_requirement_slots']) or '-'} | "
            f"{', '.join(row['selected_merged_evidence_ids']) or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 판정",
            "",
            "모든 조건이 충족되면 P26 live E2E에서 이 candidate path를 사용한다. 이 preflight는 retrieval·matcher·route/gate의 결정적 preparation만 검증하며 semantic 답변 품질은 HCX 결과를 새로 라벨링해야 한다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument(
        "--p24b-reference",
        type=Path,
        default=ROOT / "data/diagnostics/p24b_full40_shared_preparation.json",
    )
    parser.add_argument(
        "--p15-reference",
        type=Path,
        default=ROOT / "evaluation/p24b_p15_mini_holdout_results.jsonl",
    )
    parser.add_argument(
        "--p15-questions",
        type=Path,
        default=ROOT / "evaluation/p15_mini_holdout_questions.json",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p26_candidate_preflight.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p26_candidate_preflight.md")
    args = parser.parse_args()

    questions = _jsonl(args.questions)
    reference = {
        row["question_id"]: row
        for row in json.loads(args.p24b_reference.read_text(encoding="utf-8"))["rows"]
    }
    if {row["question_id"] for row in questions} != set(reference):
        raise ValueError("P26 questions and P24-B reference IDs must match")

    agent = P26CandidateAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    current = {row["question_id"]: _state(agent, row["question"]) for row in questions}
    mismatches = {
        question_id: [
            field for field in PARITY_FIELDS if current[question_id][field] != reference[question_id][field]
        ]
        for question_id in reference
    }
    mismatches = {question_id: fields for question_id, fields in mismatches.items() if fields}

    old_reference = {row["question_id"]: row for row in reference.values()}
    known_false_rejection = [
        question_id
        for question_id, row in current.items()
        if old_reference[question_id]["semantic_retrieval_sufficiency_reference"] == "full"
        and not row["evidence_sufficient"]
    ]
    known_unsafe_pass = [
        question_id
        for question_id, row in current.items()
        if old_reference[question_id]["semantic_retrieval_sufficiency_reference"] in {"partial", "none"}
        and question_id not in P24B_CURRENTLY_SUFFICIENT
        and row["evidence_sufficient"]
    ]

    p15_questions = json.loads(args.p15_questions.read_text(encoding="utf-8"))["questions"]
    p15_reference = {row["question_id"]: row for row in _jsonl(args.p15_reference)}
    p15_regressions = []
    for question in p15_questions:
        state = _state(agent, question["question"])
        expected = p15_reference[question["question_id"]]
        if (state["route"], state["evidence_sufficient"]) != (
            expected["predicted_route"], expected["gate_pass"],
        ):
            p15_regressions.append(question["question_id"])

    payload = {
        "experiment": "P26 candidate offline preflight",
        "hcx_called": False,
        "production_agent_changed": False,
        "full40_preparation_parity": f"{len(current) - len(mismatches)}/{len(current)}",
        "parity_mismatches": mismatches,
        "known_false_rejection": known_false_rejection,
        "known_unsafe_pass": known_unsafe_pass,
        "p15_route_gate_regressions": p15_regressions,
        "target_cases": [
            {"question_id": question_id, **current[question_id]}
            for question_id in sorted(P24B_CURRENTLY_SUFFICIENT)
        ],
        "go": not mismatches and not known_false_rejection and not known_unsafe_pass and not p15_regressions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("full40_preparation_parity", "known_false_rejection", "known_unsafe_pass", "p15_route_gate_regressions", "go")}, ensure_ascii=False, indent=2))
    if not payload["go"]:
        raise SystemExit("P26 candidate preflight failed; HCX execution is blocked")


if __name__ == "__main__":
    main()
