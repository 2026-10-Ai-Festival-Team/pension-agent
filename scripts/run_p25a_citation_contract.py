"""P25-A: R-002/R-006 minimal citation contract 반복 검증.

HCX 원문 응답은 Git 제외된 diagnostics 파일에만 저장한다. 이 스크립트는 Router,
RequirementBuilder, retrieval, gate 또는 validator를 변경하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.evaluation.citation_contract import classify_citation_failure
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.citation_diagnosis import CitationDiagnosisPromptBuilder
from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.errors import GenerationError, GenerationResponseError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


TARGET_IDS = ("R-002", "R-006")


def _failure_from_error(error: GenerationError) -> str:
    diagnostic = error.diagnostic or {}
    if diagnostic.get("json_parse_success") is False:
        return "malformed_json"
    if isinstance(error, GenerationResponseError):
        return "schema_failure"
    if diagnostic.get("http_status") is not None:
        return f"http_{diagnostic['http_status']}"
    return type(error).__name__


def _report(payload: dict) -> str:
    rows = payload["rows"]
    summary = payload["summary"]
    table_rows = []
    for row in rows:
        table_rows.append(
            "| {question_id} | {run_no} | {citation_parse_success} | {citation_validation_success} | {failure_reason} | {http_status} | {retry_count} | {latency_ms} |".format(
                **row
            )
        )
    return "\n".join(
        [
            "# P25-A: HCX Citation Contract 반복 검증",
            "",
            "R-002와 R-006의 selected evidence를 각각 한 번만 결정한 뒤, 같은 context 순서와 minimal citation representation으로 HCX를 3회씩 호출했다.",
            "",
            f"- 모델: `{payload['model']}`",
            f"- 표현 방식: `{payload['representation']}`",
            f"- HCX 호출 수: {summary['attempted']}",
            f"- citation validator 통과: {summary['citation_validation_pass']}/{summary['attempted']}",
            f"- JSON/schema 통과: {summary['schema_parse_pass']}/{summary['attempted']}",
            f"- full chunk_id 반환: R-002 {summary['by_question']['R-002']['full_chunk_id']}/3, R-006 {summary['by_question']['R-006']['full_chunk_id']}/3",
            "",
            "## 호출별 결과",
            "",
            "| Question | Run | JSON/schema | Citation | Failure | HTTP | Retries | Latency ms |",
            "|---|---:|---|---|---|---:|---:|---:|",
            *table_rows,
            "",
            "원문 HCX 응답과 parsed answer는 `data/diagnostics`에만 저장하며 Git에 포함하지 않는다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p25a_citation_contract_raw.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p25a_citation_contract.md")
    parser.add_argument("--execute", action="store_true", help="실제 HCX 호출을 실행한다.")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P25-A는 실제 HCX 호출을 수행합니다. 실행하려면 --execute를 지정하세요.")
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx":
        raise SystemExit("P25-A에는 GENERATOR_BACKEND=hcx가 필요합니다.")
    questions = {item.question_id: item for item in load_questions(args.questions)}
    if not set(TARGET_IDS).issubset(questions):
        raise ValueError("R-002/R-006 질문을 찾을 수 없습니다.")

    retriever = build_frozen_retriever(args.corpus, args.index)
    # selection/context는 호출 반복 전에 한 번만 결정해 HCX 변수를 citation 출력으로 한정한다.
    planner = ConditionalRoutingShadowAgent(retriever=retriever, generator=object())
    plans = {question_id: planner.prepare(questions[question_id].question, top_k=10) for question_id in TARGET_IDS}
    for question_id, plan in plans.items():
        if not plan.assessment.sufficient or plan.selection is None:
            raise RuntimeError(f"{question_id}: complete selected evidence가 없어 P25-A를 실행할 수 없습니다.")

    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)
    rows = []
    for question_id in TARGET_IDS:
        question = questions[question_id]
        plan = plans[question_id]
        contexts = list(plan.contexts)
        allowed_ids = [item.chunk_id for item in contexts]
        source_ids = [item.source_id for item in contexts]
        builder = CitationDiagnosisPromptBuilder("B_minimal_no_other_identifier", plan.selection)
        for run_no in range(1, args.repetitions + 1):
            raw_responses: list[dict] = []
            generator = HyperClovaXGenerator(
                config=settings,
                prompt_builder=builder,
                rate_limiter=limiter,
                response_capture=lambda status, body: raw_responses.append(
                    {"http_status": status, "body": body}
                ),
            )
            row = {
                "question_id": question_id,
                "run_no": run_no,
                "allowed_chunk_ids": allowed_ids,
                "context_chunk_count": len(contexts),
                "chunk_id_lengths": [len(item) for item in allowed_ids],
                "raw_hcx_response": raw_responses,
                "parsed_answer": None,
                "raw_cited_chunk_ids": None,
                "citation_parse_success": False,
                "citation_validation_success": False,
                "failure_reason": None,
                "semantic_answer_ok": "pending_manual_review",
                "latency_ms": None,
                "http_status": None,
                "retry_count": 0,
            }
            try:
                generated = generator.generate(
                    question=question.question,
                    contexts=contexts,
                    query_analysis=plan.analysis,
                )
                diagnostic = generated.diagnostic or {}
                row.update(
                    {
                        "parsed_answer": generated.answer,
                        "raw_cited_chunk_ids": generated.cited_chunk_ids,
                        "citation_parse_success": diagnostic.get("json_parse_success", True),
                        "latency_ms": round(generated.latency_ms, 3),
                        "http_status": diagnostic.get("http_status"),
                        "retry_count": max(0, diagnostic.get("attempt_count", 1) - 1),
                    }
                )
                failure = classify_citation_failure(generated.cited_chunk_ids, allowed_ids, source_ids)
                row["failure_reason"] = failure
                row["citation_validation_success"] = failure is None
            except GenerationError as error:
                diagnostic = error.diagnostic or {}
                row.update(
                    {
                        "failure_reason": _failure_from_error(error),
                        "citation_parse_success": diagnostic.get("json_parse_success", False),
                        "http_status": diagnostic.get("http_status"),
                        "retry_count": max(0, diagnostic.get("attempt_count", 1) - 1),
                    }
                )
            rows.append(row)

    by_question = {
        question_id: {
            "full_chunk_id": sum(
                row["citation_validation_success"]
                for row in rows
                if row["question_id"] == question_id
            ),
        }
        for question_id in TARGET_IDS
    }
    summary = {
        "attempted": len(rows),
        "citation_validation_pass": sum(row["citation_validation_success"] for row in rows),
        "schema_parse_pass": sum(row["citation_parse_success"] for row in rows),
        "by_question": by_question,
    }
    payload = {
        "experiment": "P25-A citation contract",
        "model": settings.hcx_model,
        "representation": "B_minimal_no_other_identifier",
        "hcx_called": True,
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
