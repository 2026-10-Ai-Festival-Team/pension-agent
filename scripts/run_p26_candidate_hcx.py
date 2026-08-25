"""P26 candidate path의 HCX-007 Full-40 controlled E2E 실행기."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent
from src.evaluation.provider_incident import add_sliding_window_counts
from src.evaluation.provider_stability import attach_request_spacing, summarize_provider_attempts
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.generation.factory import build_answer_generator
from src.orchestration.retrieval_service import build_frozen_retriever

PREPARATION_FIELDS = (
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


def _attempts(rows: list[dict]) -> list[dict]:
    attempts = []
    for row in rows:
        for item in row.get("generation_attempt_history", []):
            attempt = dict(item)
            attempt["question_id"] = row["question_id"]
            attempt["global_request_start_offset_ms"] = attempt.get("request_started_monotonic_ms")
            attempt["global_request_completed_offset_ms"] = attempt.get("request_completed_monotonic_ms")
            attempts.append(attempt)
    if not attempts:
        return []
    origin = min(item["global_request_start_offset_ms"] for item in attempts if item["global_request_start_offset_ms"] is not None)
    for item in attempts:
        if item["global_request_start_offset_ms"] is not None:
            item["global_request_start_offset_ms"] = round(item["global_request_start_offset_ms"] - origin, 3)
        if item["global_request_completed_offset_ms"] is not None:
            item["global_request_completed_offset_ms"] = round(item["global_request_completed_offset_ms"] - origin, 3)
    return add_sliding_window_counts(
        attach_request_spacing(attempts), windows_ms=(30_000, 60_000, 120_000)
    )


def _preparation_state(row: dict) -> dict:
    requirement_plan = row.get("requirement_plan") or {"category": None, "slots": []}
    trace = {
        "route": row.get("route"),
        "extracted_entities": row.get("extracted_entities"),
        "requirement_plan": {
            "category": requirement_plan.get("category"),
            "slots": [
                {
                    "name": slot.get("name"),
                    "key": slot.get("key"),
                    "terms": slot.get("terms", []),
                    "min_matches": slot.get("min_matches"),
                    "retrieval_query": slot.get("retrieval_query"),
                }
                for slot in requirement_plan.get("slots", [])
            ],
        },
        "base_retrieved_chunk_ids": row.get("base_retrieved_chunk_ids", []),
        "candidate_chunk_ids": row.get("candidate_chunk_ids", []),
        "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
        "evidence_sufficient": row.get("evidence_sufficient"),
        "gate_decision": row.get("evidence_reason"),
        "missing_requirement_slots": row.get("missing_requirement_slots", []),
        "hcx_would_be_invoked": row.get("generator_attempted", False),
    }
    return trace


def _markdown(payload: dict) -> str:
    provider = payload["provider_summary"]
    return "\n".join(
        [
            "# P26: P24-B Candidate HCX E2E 실행",
            "",
            "P24-B retrieval/matcher를 P26 candidate evaluation path에만 포함했다. 기본 브라우저 Agent는 변경하지 않았다. 이 문서는 실행·안정성 결과이며, 새 답변의 semantic quality는 별도 수동 라벨링 전에는 확정하지 않는다.",
            "",
            "## 고정 조건",
            "",
            f"- 모델: `{payload['model']}`",
            "- P24-B requirement retrieval/matcher candidate",
            "- provenance·금융 답변 정책",
            "- P25-A minimal citation representation 및 strict validator",
            "- HCX request-start 최소 간격: 6초 (guard 0.1초)",
            "",
            "## Preparation",
            "",
            f"- P24-B reference parity: {payload['preparation_parity']}",
            f"- known false rejection: {payload['known_false_rejection_count']}",
            f"- known unsafe pass: {payload['known_unsafe_pass_count']}",
            "",
            "## Provider 실행 결과",
            "",
            f"- 질문: {payload['question_count']}개",
            f"- HCX 호출 대상: {provider['generator_attempted']}개",
            f"- 정책상 사전 차단: {provider['policy_blocked']}개",
            f"- provider attempt: {provider['provider_attempts']}개",
            f"- HTTP 200 / 429 / 5xx: {provider['http_200']} / {provider['http_429']} / {provider['http_5xx']}",
            f"- provider retry exhaustion: {provider['retry_exhaustion']}",
            f"- 최소 request-start 간격(ms): {provider['min_request_start_delta_ms']}",
            "",
            "## 다음 단계",
            "",
            "`evaluation/p26_candidate_execution.jsonl`의 answer hash별로 semantic correctness, requirement coverage, grounding, answer relevance, hallucination, information-limit handling을 새로 라벨링한다. 이 단계가 끝나기 전에는 Strict E2E Useful 또는 production 승격을 선언하지 않는다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="실제 HCX 비용이 발생한다.")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument(
        "--p24b-reference",
        type=Path,
        default=ROOT / "data/diagnostics/p24b_full40_shared_preparation.json",
    )
    parser.add_argument(
        "--preflight",
        type=Path,
        default=ROOT / "evaluation/p26_candidate_preflight.json",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=ROOT / "data/diagnostics/p26_candidate_hcx_raw.json",
    )
    parser.add_argument(
        "--label-output",
        type=Path,
        default=ROOT / "evaluation/p26_candidate_execution.jsonl",
    )
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p26_candidate_hcx_execution.md")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P26은 실제 HCX 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P26에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    questions = load_questions(args.questions)
    preflight = json.loads(args.preflight.read_text(encoding="utf-8"))
    if not preflight.get("go"):
        raise SystemExit("P26 candidate preflight가 통과하지 않아 HCX 실행을 차단했습니다.")
    reference = {
        row["question_id"]
        for row in json.loads(args.p24b_reference.read_text(encoding="utf-8"))["rows"]
    }
    if {question.question_id for question in questions} != reference:
        raise ValueError("P26 questions and P24-B reference IDs must match")

    agent = P26CandidateAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=build_answer_generator(settings),
    )
    started = time.perf_counter()
    rows = evaluate_agent(TestClient(create_app(agent)), questions)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    attempts = _attempts(rows)
    telemetry = summarize_provider_attempts(attempts)
    provider_summary = {
        **telemetry,
        "generator_attempted": sum(row["generator_attempted"] for row in rows),
        "policy_blocked": sum(not row["generator_attempted"] for row in rows),
    }

    reference_rows = {
        row["question_id"]: row
        for row in json.loads(args.p24b_reference.read_text(encoding="utf-8"))["rows"]
    }
    parity = []
    for row in rows:
        actual = _preparation_state(row)
        expected = {field: reference_rows[row["question_id"]][field] for field in PREPARATION_FIELDS}
        mismatches = [field for field in PREPARATION_FIELDS if actual[field] != expected[field]]
        parity.append({"question_id": row["question_id"], "parity": not mismatches, "mismatches": mismatches})

    payload = {
        "experiment": "P26 P24-B candidate controlled HCX E2E",
        "hcx_called": True,
        "model": settings.hcx_model,
        "settings": {
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "pacing_guard_seconds": settings.hcx_pacing_guard_seconds,
            "max_retries": settings.max_retries,
        },
        "question_count": len(rows),
        "duration_ms": duration_ms,
        "preparation_parity": f"{sum(item['parity'] for item in parity)}/{len(parity)}",
        "preparation_deltas": parity,
        "known_false_rejection_count": len(preflight["known_false_rejection"]),
        "known_unsafe_pass_count": len(preflight["known_unsafe_pass"]),
        "provider_summary": provider_summary,
        "rows": rows,
        "attempt_telemetry": attempts,
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.label_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.label_output.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    {
                        "question_id": row["question_id"],
                        "question": next(question.question for question in questions if question.question_id == row["question_id"]),
                        "answer": row["answer"],
                        "answer_hash": hashlib.sha256(row["answer"].encode("utf-8")).hexdigest(),
                        "route": row.get("route"),
                        "evidence_sufficient": row.get("evidence_sufficient"),
                        "generator_called": row.get("generator_called"),
                        "citation_valid": row.get("citation_valid"),
                        "cited_chunk_ids": row.get("cited_chunk_ids", []),
                        "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
                        "semantic_correctness": "pending_manual_review",
                        "requirement_coverage": "pending_manual_review",
                        "grounding": "pending_manual_review",
                        "answer_relevance": "pending_manual_review",
                        "hallucination": "pending_manual_review",
                        "information_limit_handling": "pending_manual_review",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    args.report.write_text(_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "preparation_parity": payload["preparation_parity"],
                "provider_summary": provider_summary,
                "duration_ms": duration_ms,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if payload["preparation_parity"] != f"{len(rows)}/{len(rows)}":
        raise SystemExit("P26 preparation parity failed; E2E results retained for diagnosis")


if __name__ == "__main__":
    main()
