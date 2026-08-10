"""P7: DASH-002에서 기존 Context와 merged Context를 제한 비교한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.experiments.decomposed_retrieval import retrieve_by_requirement
from src.experiments.multi_evidence import (
    CitationBindingPromptBuilder,
    EvidenceSelection,
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


def generate(question, selection, settings, limiter):
    row = {**selection_record(selection), "generator_called": False, "citation_valid": False, "answer": None, "generation_error": None}
    try:
        result = HyperClovaXGenerator(
            config=settings, prompt_builder=CitationBindingPromptBuilder(selection), rate_limiter=limiter
        ).generate(question=question.question, contexts=list(selection.contexts), query_analysis=QueryAnalyzer().analyze(question.question))
        allowed = {context.chunk_id for context in selection.contexts}
        valid = bool(result.cited_chunk_ids) and set(result.cited_chunk_ids).issubset(allowed)
        row.update({
            "generator_called": valid,
            "citation_valid": valid,
            "returned_cited_chunk_ids": result.cited_chunk_ids,
            "answer": result.answer if valid else None,
            "generation_error": None if valid else "CitationValidationError",
            "generation_latency_ms": round(result.latency_ms, 3),
            "generation_usage": result.usage,
            "generation_diagnostic": result.diagnostic,
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
    parser.add_argument("--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--plans", type=Path, default=ROOT / "evaluation/p6_decomposed_retrieval_cases.json")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p7_merged_context_hcx_pilot.json")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P7 주 실험은 HCX-DASH-002로만 실행합니다.")
    questions = {item.question_id: item for item in load_questions(args.questions)}
    requirements = {item.question_id: item for item in load_requirement_cases(args.requirements)}
    plans = {item["question_id"]: item["slot_queries"] for item in json.loads(args.plans.read_text(encoding="utf-8"))["cases"]}
    retriever = build_frozen_retriever(args.corpus, args.index)
    selector = RequirementEvidenceSelector()
    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)
    rows = []
    for question_id in ("R-037", "R-028"):
        question = questions[question_id]
        case = requirements[question_id]
        existing_results = tuple(retriever.search(question.question, top_k=10).results)
        existing_matches = selector.select(case, existing_results)
        # Preserve the prior Agent's context budget for A, while retaining the
        # requirement map for an explicit evidence-completeness diagnostic.
        baseline = EvidenceSelection(case, existing_matches.matches, existing_results[:5])
        decomposed = retrieve_by_requirement(retriever, plans[question_id], top_k=10)
        merged = selector.select(case, decomposed.merged_results)
        for run_number in range(1, args.runs + 1):
            rows.append({"question_id": question_id, "variant": "A_existing_top5", "run": run_number, **generate(question, baseline, settings, limiter)})
            rows.append({"question_id": question_id, "variant": "B_decomposed_merged", "run": run_number, **generate(question, merged, settings, limiter)})

    # R-024 is a negative control: record the failed evidence gate and do not call HCX.
    question = questions["R-024"]
    case = requirements["R-024"]
    decomposed = retrieve_by_requirement(retriever, plans["R-024"], top_k=10)
    negative = selector.select(case, decomposed.merged_results)
    rows.append({"question_id": "R-024", "variant": "negative_retrieval_missing", "run": None, **selection_record(negative), "generator_called": False, "citation_valid": None, "answer": None, "generation_error": None, "status": "blocked_incomplete_requirement_evidence"})
    payload = {"experiment": "P7 merged-context HCX pilot", "model": settings.hcx_model, "runs_per_variant": args.runs, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"model": settings.hcx_model, "rows": len(rows), "accepted": sum(row["status"] == "accepted" for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
