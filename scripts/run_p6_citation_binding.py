"""P6-A citation binding 실험. 기본 대상은 R-002와 R-011이다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.experiments.multi_evidence import (
    CitationBindingPromptBuilder,
    RequirementEvidenceSelector,
    load_requirement_cases,
    selection_record,
)
from src.generation.errors import GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def run_case(case, question, retriever, settings, limiter):
    results = retriever.search(question.question, top_k=10).results
    selection = RequirementEvidenceSelector().select(case, results)
    row = {
        "question_id": case.question_id,
        "question": question.question,
        "top10_chunk_ids": [item.chunk_id for item in results],
        **selection_record(selection),
        "generator_called": False,
        "citation_valid": False,
        "generation_error": None,
        "answer": None,
    }
    if not selection.complete:
        row["status"] = "blocked_incomplete_requirement_evidence"
        return row
    try:
        generated = HyperClovaXGenerator(
            config=settings,
            prompt_builder=CitationBindingPromptBuilder(selection),
            rate_limiter=limiter,
        ).generate(
            question=question.question,
            contexts=list(selection.contexts),
            query_analysis=QueryAnalyzer().analyze(question.question),
        )
        allowed = {item.chunk_id for item in selection.contexts}
        valid = bool(generated.cited_chunk_ids) and set(generated.cited_chunk_ids).issubset(allowed)
        row.update({
            "generator_called": valid,
            "citation_valid": valid,
            "returned_cited_chunk_ids": generated.cited_chunk_ids,
            "generation_latency_ms": round(generated.latency_ms, 3),
            "generation_usage": generated.usage,
            "generation_diagnostic": generated.diagnostic,
            "answer": generated.answer if valid else None,
            "generation_error": None if valid else "CitationValidationError",
            "status": "accepted" if valid else "rejected_invalid_citation",
        })
    except GenerationError as error:
        row.update({"generation_error": type(error).__name__, "generation_diagnostic": error.diagnostic, "status": "generation_failure"})
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--cases", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p6_citation_binding_run.json")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx":
        raise SystemExit("P6-A에는 GENERATOR_BACKEND=hcx가 필요합니다.")
    cases = {case.question_id: case for case in load_requirement_cases(args.cases)}
    target_ids = ("R-002", "R-011")
    questions = {item.question_id: item for item in load_questions(args.questions)}
    retriever = build_frozen_retriever(args.corpus, args.index)
    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)
    rows = [run_case(cases[item], questions[item], retriever, settings, limiter) for item in target_ids]
    payload = {"experiment": "P6-A citation binding", "rows": rows, "accepted": sum(row["status"] == "accepted" for row in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(rows), "accepted": payload["accepted"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
