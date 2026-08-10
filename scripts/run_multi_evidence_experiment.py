"""P5 multi-evidence orchestration A/B 실험을 재현한다.

기본 실행은 네트워크 호출 없이 Top-10 슬롯 coverage만 기록한다. ``--execute``는
generation_enabled인 dev target/control 사례에만 실제 HCX를 한 번씩 호출한다.
감사 전용 test 사례는 어떤 경우에도 HCX 호출을 하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.generation.errors import GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.experiments.multi_evidence import (
    RequirementAwarePromptBuilder,
    RequirementEvidenceSelector,
    load_requirement_cases,
    selection_record,
)
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def run_case(case, question, retriever, selector, *, execute, settings=None, limiter=None):
    response = retriever.search(question.question, top_k=10)
    selection = selector.select(case, response.results)
    row = {
        "question_id": case.question_id,
        "role": case.role,
        "question": question.question,
        "top10_chunk_ids": [item.chunk_id for item in response.results],
        **selection_record(selection),
        "generation_attempted": False,
        "generator_called": False,
        "generation_error": None,
        "citation_valid": None,
        "generation_latency_ms": None,
        "generation_usage": None,
        "answer": None,
    }
    if not case.generation_enabled:
        row["experiment_status"] = "audit_only"
        return row
    if not selection.complete:
        row["experiment_status"] = "blocked_incomplete_requirement_evidence"
        return row
    if not execute:
        row["experiment_status"] = "dry_run_ready"
        return row

    row["generation_attempted"] = True
    generator = HyperClovaXGenerator(
        config=settings,
        prompt_builder=RequirementAwarePromptBuilder(selection),
        rate_limiter=limiter,
    )
    try:
        generated = generator.generate(
            question=question.question,
            contexts=list(selection.contexts),
            query_analysis=QueryAnalyzer().analyze(question.question),
        )
        allowed_ids = {item.chunk_id for item in selection.contexts}
        citation_valid = bool(generated.cited_chunk_ids) and set(generated.cited_chunk_ids).issubset(allowed_ids)
        row.update(
            {
                "generator_called": citation_valid,
                "citation_valid": citation_valid,
                "generation_error": None if citation_valid else "CitationValidationError",
                "generation_latency_ms": round(generated.latency_ms, 3),
                "generation_usage": generated.usage,
                "generation_diagnostic": generated.diagnostic,
                "answer": generated.answer if citation_valid else None,
                "returned_cited_chunk_ids": generated.cited_chunk_ids,
                "experiment_status": "accepted" if citation_valid else "rejected_invalid_citation",
            }
        )
    except GenerationError as error:
        row.update(
            {
                "generation_error": type(error).__name__,
                "generation_diagnostic": error.diagnostic,
                "experiment_status": "generation_failure",
            }
        )
    return row


def summarize(rows):
    enabled = [row for row in rows if row["role"] in {"target", "control_single_evidence"}]
    completed = [row for row in enabled if row["generation_attempted"]]
    return {
        "case_count": len(rows),
        "generation_eligible_cases": len(enabled),
        "requirement_complete_cases": sum(row["requirement_evidence_complete"] for row in rows),
        "generation_attempted": sum(row["generation_attempted"] for row in rows),
        "accepted_answers": sum(row["experiment_status"] == "accepted" for row in rows),
        "blocked_for_incomplete_evidence": sum(row["experiment_status"] == "blocked_incomplete_requirement_evidence" for row in rows),
        "audit_only_cases": sum(row["experiment_status"] == "audit_only" for row in rows),
        "completed_generation_cases": len(completed),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p5_multi_evidence_run.json")
    parser.add_argument("--execute", action="store_true", help="실제 HCX를 호출한다.")
    args = parser.parse_args()

    cases = load_requirement_cases(args.cases)
    questions = {question.question_id: question for question in load_questions(args.questions)}
    missing = [case.question_id for case in cases if case.question_id not in questions]
    if missing:
        raise SystemExit(f"질문 파일에 없는 P5 case: {', '.join(missing)}")
    settings = None
    limiter = None
    if args.execute:
        load_dotenv(ROOT / ".env")
        settings = GenerationSettings.from_env()
        if settings.generator_backend != "hcx":
            raise SystemExit("P5 --execute에는 GENERATOR_BACKEND=hcx가 필요합니다.")
        limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)

    retriever = build_frozen_retriever(args.corpus, args.index)
    selector = RequirementEvidenceSelector()
    rows = []
    for case in cases:
        rows.append(run_case(case, questions[case.question_id], retriever, selector, execute=args.execute, settings=settings, limiter=limiter))

    payload = {
        "experiment": "P5 multi-evidence orchestration",
        "executed": args.execute,
        "created_at_epoch": round(time.time(), 3),
        "summary": summarize(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
