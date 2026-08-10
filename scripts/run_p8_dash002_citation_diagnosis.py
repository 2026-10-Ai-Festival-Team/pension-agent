"""P8-A: R-028 한 건으로 DASH-002 citation ID 출력 조건을 비교한다."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.generation import GenerationSettings
from src.experiments.citation_diagnosis import CitationDiagnosisPromptBuilder, prompt_identifier_exposure
from src.experiments.decomposed_retrieval import retrieve_by_requirement
from src.experiments.multi_evidence import RequirementEvidenceSelector, load_requirement_cases, selection_record
from src.generation.errors import GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


VARIANTS = ("A_p7_current", "B_minimal_no_other_identifier", "C_delimited_citation_id", "D_explicit_json_whitelist")


def run_variant(variant, question, selection, settings, limiter):
    builder = CitationDiagnosisPromptBuilder(variant, selection)
    prompt = builder.build(question.question, list(selection.contexts))
    row = {"variant": variant, **selection_record(selection), "prompt_exposure": prompt_identifier_exposure(prompt, selection.contexts)}
    try:
        result = HyperClovaXGenerator(config=settings, prompt_builder=builder, rate_limiter=limiter).generate(
            question=question.question, contexts=list(selection.contexts), query_analysis=QueryAnalyzer().analyze(question.question)
        )
        allowed = {item.chunk_id for item in selection.contexts}
        valid = bool(result.cited_chunk_ids) and set(result.cited_chunk_ids).issubset(allowed)
        row.update({
            "status": "accepted" if valid else "rejected_invalid_citation",
            "returned_cited_chunk_ids": result.cited_chunk_ids,
            "citation_valid": valid,
            "answer": result.answer if valid else None,
            "generation_latency_ms": round(result.latency_ms, 3),
            "generation_usage": result.usage,
            "generation_diagnostic": result.diagnostic,
        })
    except GenerationError as error:
        row.update({"status": "generation_failure", "citation_valid": False, "answer": None, "generation_diagnostic": error.diagnostic, "generation_error": type(error).__name__})
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--plans", type=Path, default=ROOT / "evaluation/p6_decomposed_retrieval_cases.json")
    parser.add_argument("--question-id", choices=("R-028", "R-037"), default="R-028")
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p8_dash002_citation_diagnosis.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P8-A는 HCX-DASH-002로만 실행합니다.")
    question = next(item for item in load_questions(args.questions) if item.question_id == args.question_id)
    case = next(item for item in load_requirement_cases(args.requirements) if item.question_id == args.question_id)
    plans = {item["question_id"]: item["slot_queries"] for item in json.loads(args.plans.read_text(encoding="utf-8"))["cases"]}
    retriever = build_frozen_retriever(args.corpus, args.index)
    merged = retrieve_by_requirement(retriever, plans[args.question_id], top_k=10)
    selection = RequirementEvidenceSelector().select(case, merged.merged_results)
    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)
    rows = [run_variant(variant, question, selection, settings, limiter) for variant in args.variants]
    payload = {"experiment": "P8-A DASH-002 citation identifier diagnosis", "question_id": args.question_id, "model": settings.hcx_model, "rows": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"variants": len(rows), "accepted": sum(row["status"] == "accepted" for row in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
