"""P30 requirement planner의 제한적 HCX semantic 재평가 실행기.

Full-40 또는 production Agent를 변경하지 않는다. P30 planner/field boundary가
실제로 HCX 답변의 requirement coverage를 개선하는지 보기 위한 4개 target,
R-019 fail-closed control, 그리고 정상 control만 순차 실행한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


TARGETS = ("R-011", "R-035", "R-038", "R-034")
FAIL_CLOSED_CONTROL = "R-019"
CONTROLS = ("R-001", "R-002", "R-004", "R-008")


class ResponseCapture:
    def __init__(self) -> None:
        self.responses: list[dict] = []

    def reset(self) -> None:
        self.responses = []

    def __call__(self, status: int, body: str) -> None:
        self.responses.append({"http_status": status, "body": body})


def _row(question, role: str, response: dict, raw_attempts: list[dict]) -> dict:
    trace = response["think_trace"]
    diagnostic = trace.get("generation_diagnostic") or {}
    cited = list(trace.get("cited_chunk_ids") or [])
    contract_failures = list(diagnostic.get("response_contract_failures") or [])
    answer = response["answer"]
    return {
        "question_id": question.question_id,
        "question": question.question,
        "role": role,
        "route": trace.get("route"),
        "requirement_slots": trace.get("selected_requirement_slots", []),
        "selected_evidence_ids": trace.get("selected_merged_evidence_ids", []),
        "evidence_sufficient": trace.get("evidence_sufficient"),
        "gate_decision": trace.get("assessment_reason"),
        "missing_requirement_slots": trace.get("missing_requirement_slots", []),
        "generator_attempted": trace.get("generator_attempted"),
        "generator_called": trace.get("generator_called"),
        "generation_error": trace.get("generation_error"),
        "http_statuses": [item["http_status"] for item in raw_attempts],
        "retry_count": max(0, len(raw_attempts) - 1),
        "schema_success": bool(trace.get("generator_attempted")) and trace.get("generation_error") is None,
        "citation_validation_success": bool(cited) and trace.get("generation_error") is None,
        "cited_chunk_ids": cited,
        "answer": answer,
        "answer_hash": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "semantic_correctness": "pending_manual_review",
        "requirement_coverage": "pending_manual_review",
        "grounding": "pending_manual_review",
        "strict_useful": "pending_manual_review",
        "failure_reason": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--raw-output", type=Path, default=ROOT / "data/diagnostics/p30_live_raw.json")
    parser.add_argument("--review-output", type=Path, default=ROOT / "evaluation/p30_live_semantic_candidate.jsonl")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P30-Live는 실제 HCX 비용이 발생합니다. --execute가 필요합니다.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P30-Live에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    questions = {item.question_id: item for item in load_questions(args.questions)}
    case_ids = TARGETS + (FAIL_CLOSED_CONTROL,) + CONTROLS
    missing = sorted(set(case_ids) - set(questions))
    if missing:
        raise SystemExit(f"P30-Live 질문을 찾을 수 없습니다: {', '.join(missing)}")

    capture = ResponseCapture()
    generator = HyperClovaXGenerator(
        config=settings,
        prompt_builder=NativeStructuredOutputPromptBuilder(),
        rate_limiter=GlobalMinIntervalLimiter(
            settings.hcx_min_interval_seconds,
            guard_seconds=settings.hcx_pacing_guard_seconds,
        ),
        response_capture=capture,
    )
    agent = P27DStructuredOutputAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=generator,
    )

    rows, raw_responses = [], []
    for question_id in case_ids:
        question = questions[question_id]
        role = "target" if question_id in TARGETS else "fail_closed_control" if question_id == FAIL_CLOSED_CONTROL else "control"
        capture.reset()
        response = agent.answer(question.question, top_k=10)
        rows.append(_row(question, role, response, list(capture.responses)))
        raw_responses.append({"question_id": question_id, "responses": list(capture.responses)})

    summary = {
        "questions": len(rows),
        "hcx_attempted": sum(bool(row["generator_attempted"]) for row in rows),
        "schema_success": sum(bool(row["schema_success"]) for row in rows),
        "citation_validation_success": sum(bool(row["citation_validation_success"]) for row in rows),
        "provider_429": sum(status == 429 for row in rows for status in row["http_statuses"]),
        "provider_5xx": sum(status >= 500 for row in rows for status in row["http_statuses"]),
        "fail_closed_control_called_hcx": next(
            row["generator_called"] for row in rows if row["question_id"] == FAIL_CLOSED_CONTROL
        ),
    }
    payload = {
        "experiment": "P30 live limited HCX semantic reevaluation",
        "hcx_called": True,
        "model": settings.hcx_model,
        "fixed_conditions": {
            "requirement_planner": "P30 candidate",
            "product_field_boundary": "P30 candidate",
            "native_structured_outputs": True,
            "thinking_effort": "none",
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "parser": "strict_fail_closed",
            "citation_validator": "strict_subset",
            "workflow": "disabled",
        },
        "summary": summary,
        "rows": rows,
        "raw_hcx_responses": raw_responses,
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.review_output.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["fail_closed_control_called_hcx"]:
        raise SystemExit("R-019 fail-closed control unexpectedly called HCX")


if __name__ == "__main__":
    main()
