"""P27-D: HCX-007 native Structured Outputs 형식 안정성 A/B 실행기.

현재 JSON prompt(A)와 API-level JSON Schema(B)를 동일 P26 candidate preparation
결과에서 비교한다. strict parser·citation validator는 전혀 완화하지 않는다.
원문 HCX body는 Git 제외 diagnostics에만 저장한다.
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
from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder, PromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


FORMAT_FAILURE_CASES = ("R-001", "R-004", "R-007", "R-011", "R-022", "R-025")
CONTROL_CASES = ("R-002", "R-019", "R-024", "R-037")


class _ResponseCapture:
    def __init__(self) -> None:
        self.current: list[dict] = []

    def reset(self) -> None:
        self.current = []

    def __call__(self, status, body) -> None:
        self.current.append({"http_status": status, "body": body})


def _content_shape(raw_responses: list[dict]) -> dict:
    contents = []
    for item in raw_responses:
        try:
            data = json.loads(item["body"])
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
        result = data.get("result", {}) if isinstance(data, dict) else {}
        message = result.get("message", {}) if isinstance(result, dict) else {}
        content = (
            message.get("content")
            or data.get("message", {}).get("content")
            or data.get("choices", [{}])[0].get("message", {}).get("content")
        )
        if isinstance(content, str):
            contents.append(content)
    content = contents[-1] if contents else ""
    first_object = content.find("{")
    prefix = content[:first_object].strip() if first_object >= 0 else content.strip()
    return {
        "raw_content_present": bool(contents),
        "raw_content_has_markdown_fence": "```" in content,
        "raw_content_has_prefix_prose": bool(prefix),
        "raw_content_length": len(content) if contents else None,
    }


def _make_agent(settings, variant: str, capture: _ResponseCapture, corpus: Path, index: Path):
    limiter = GlobalMinIntervalLimiter(
        settings.hcx_min_interval_seconds,
        guard_seconds=settings.hcx_pacing_guard_seconds,
    )
    builder = PromptBuilder() if variant == "A_current_json_prompt" else NativeStructuredOutputPromptBuilder()
    generator = HyperClovaXGenerator(
        config=settings,
        prompt_builder=builder,
        rate_limiter=limiter,
        response_capture=capture,
    )
    agent_type = P26CandidateAgent if variant == "A_current_json_prompt" else P27DStructuredOutputAgent
    return agent_type(retriever=build_frozen_retriever(corpus, index), generator=generator)


def _row(question, role: str, run_no: int, response: dict, raw_responses: list[dict]) -> dict:
    trace = response["think_trace"]
    diagnostic = trace.get("generation_diagnostic") or {}
    contract_failures = list(diagnostic.get("response_contract_failures") or [])
    shape = _content_shape(raw_responses)
    attempted = bool(trace.get("generator_attempted"))
    error = trace.get("generation_error")
    cited = list(trace.get("cited_chunk_ids") or [])
    return {
        "question_id": question.question_id,
        "question": question.question,
        "case_role": role,
        "run_no": run_no,
        "route": trace.get("route"),
        "requirement_slots": trace.get("selected_requirement_slots", []),
        "selected_merged_evidence_ids": trace.get("selected_merged_evidence_ids", []),
        "evidence_sufficient": trace.get("evidence_sufficient"),
        "generator_attempted": attempted,
        "generator_called": bool(trace.get("generator_called")),
        "generation_error": error,
        "json_schema_success": attempted and error is None,
        "json_parse_success": diagnostic.get("json_parse_success"),
        "response_contract_failures": contract_failures,
        "empty_answer": "empty_answer" in contract_failures,
        "empty_citation_array": "empty_cited_chunk_ids" in contract_failures,
        "citation_validation_success": attempted and error is None and bool(cited),
        "cited_chunk_ids": cited,
        "generation_latency_ms": trace.get("generation_latency_ms"),
        "http_statuses": [item["http_status"] for item in raw_responses],
        "retry_count": max(0, len(raw_responses) - 1),
        "answer": response["answer"],
        "answer_hash": hashlib.sha256(response["answer"].encode("utf-8")).hexdigest(),
        "semantic_correctness": "pending_manual_review",
        "requirement_coverage": "pending_manual_review",
        "grounding": "pending_manual_review",
        **shape,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("A_current_json_prompt", "B_native_structured_output"), required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--label-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P27-D는 실제 HCX 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")
    if args.repetitions < 2:
        raise SystemExit("P27-D는 비결정성 확인을 위해 최소 2회 반복합니다.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P27-D에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    questions = {item.question_id: item for item in load_questions(args.questions)}
    case_ids = FORMAT_FAILURE_CASES + CONTROL_CASES
    missing = [item for item in case_ids if item not in questions]
    if missing:
        raise SystemExit(f"P27-D 질문을 찾을 수 없습니다: {missing}")

    capture = _ResponseCapture()
    agent = _make_agent(settings, args.variant, capture, args.corpus, args.index)
    rows = []
    raw_hcx_responses = []
    for question_id in case_ids:
        question = questions[question_id]
        role = "format_failure" if question_id in FORMAT_FAILURE_CASES else "semantic_control"
        for run_no in range(1, args.repetitions + 1):
            capture.reset()
            response = agent.answer(question.question, top_k=10)
            rows.append(_row(question, role, run_no, response, capture.current))
            raw_hcx_responses.append(
                {
                    "question_id": question_id,
                    "run_no": run_no,
                    "responses": list(capture.current),
                }
            )

    summary = {
        "calls": len(rows),
        "json_schema_success": sum(row["json_schema_success"] for row in rows),
        "citation_validation_success": sum(row["citation_validation_success"] for row in rows),
        "prefix_prose": sum(row["raw_content_has_prefix_prose"] for row in rows),
        "markdown_fence": sum(row["raw_content_has_markdown_fence"] for row in rows),
        "empty_answer": sum(row["empty_answer"] for row in rows),
        "empty_citation_array": sum(row["empty_citation_array"] for row in rows),
        "http_429": sum(status == 429 for row in rows for status in row["http_statuses"]),
    }
    payload = {
        "experiment": "P27-D HCX-007 native Structured Outputs A/B",
        "variant": args.variant,
        "hcx_called": True,
        "model": settings.hcx_model,
        "repetitions": args.repetitions,
        "fixed_conditions": {
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "max_retries": settings.max_retries,
            "parser": "strict_fail_closed",
            "citation_validator": "strict_subset",
            "thinking": "effort_none (native SO compatibility)" if args.variant == "B_native_structured_output" else "effort_none",
        },
        "summary": summary,
        "rows": rows,
        "raw_hcx_responses": raw_hcx_responses,
    }
    # Raw bodies are kept out of the review artifact; write them only to the
    # Git-ignored diagnostics output supplied by the caller.
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.label_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.label_output.open("w", encoding="utf-8") as output:
        for row in rows:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"variant": args.variant, **summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
