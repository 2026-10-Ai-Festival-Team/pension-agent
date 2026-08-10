"""P8-B: 동일 merged evidence에서 current/minimal citation 표현을 비교한다."""
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
from src.experiments.multi_evidence import CitationBindingPromptBuilder, RequirementEvidenceSelector, load_requirement_cases, selection_record
from src.generation.errors import GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever
from src.evaluation.retrieval_dataset import load_questions


def build_prompt_builder(representation, selection):
    if representation == "A_current":
        return CitationBindingPromptBuilder(selection)
    if representation == "B_minimal":
        return CitationDiagnosisPromptBuilder("B_minimal_no_other_identifier", selection)
    raise ValueError(representation)


def run_generation(representation, question, selection, settings, limiter):
    builder = build_prompt_builder(representation, selection)
    prompt = builder.build(question.question, list(selection.contexts))
    row = {
        "representation": representation,
        "prompt_size_chars": len(prompt),
        "prompt_exposure": prompt_identifier_exposure(prompt, selection.contexts),
        "semantic_correctness": "pending_manual_review",
        "requirement_coverage": "pending_manual_review",
        "grounding": "pending_manual_review",
        "answer_relevance": "pending_manual_review",
        "hallucination": "pending_manual_review",
    }
    try:
        generated = HyperClovaXGenerator(config=settings, prompt_builder=builder, rate_limiter=limiter).generate(
            question=question.question, contexts=list(selection.contexts), query_analysis=QueryAnalyzer().analyze(question.question)
        )
        allowed = {item.chunk_id for item in selection.contexts}
        valid = bool(generated.cited_chunk_ids) and set(generated.cited_chunk_ids).issubset(allowed)
        row.update({
            "status": "accepted" if valid else "rejected_invalid_citation",
            "raw_cited_chunk_ids": generated.cited_chunk_ids,
            "citation_validation_pass": valid,
            "citation_failure_kind": None if valid else "source_prefix_or_unknown_or_missing",
            "answer": generated.answer if valid else None,
            "generation_latency_ms": round(generated.latency_ms, 3),
            "generation_usage": generated.usage,
            "generation_diagnostic": generated.diagnostic,
        })
    except GenerationError as error:
        row.update({"status": "generation_failure", "citation_validation_pass": False, "citation_failure_kind": type(error).__name__, "answer": None, "generation_diagnostic": error.diagnostic})
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json")
    parser.add_argument("--subset", type=Path, default=ROOT / "evaluation/p8b_compound_dev_subset.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p8b_compound_citation_stability.json")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P8-B는 HCX-DASH-002로만 실행합니다.")
    questions = {item.question_id: item for item in load_questions(args.questions)}
    requirements = {item.question_id: item for item in load_requirement_cases(args.requirements)}
    plans = json.loads(args.subset.read_text(encoding="utf-8"))["cases"]
    retriever = build_frozen_retriever(args.corpus, args.index)
    selector = RequirementEvidenceSelector()
    limiter = GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds)
    rows = []
    for plan in plans:
        question_id = plan["question_id"]
        question = questions[question_id]
        selection = selector.select(
            requirements[question_id], retrieve_by_requirement(retriever, plan["slot_queries"], top_k=10).merged_results
        )
        base = {"question_id": question_id, "group": plan["group"], **selection_record(selection)}
        if plan["repetitions"] == 0:
            rows.append({
                **base, "repetition": None, "representation": None,
                "status": "blocked_incomplete_requirement_evidence" if not selection.complete else "negative_control_not_generated",
                "citation_validation_pass": None, "semantic_correctness": "not_applicable", "answer": None,
            })
            continue
        if not selection.complete:
            rows.append({**base, "repetition": None, "representation": None, "status": "blocked_incomplete_requirement_evidence", "citation_validation_pass": None, "semantic_correctness": "not_applicable", "answer": None})
            continue
        for repetition in range(1, plan["repetitions"] + 1):
            for representation in ("A_current", "B_minimal"):
                rows.append({**base, "repetition": repetition, **run_generation(representation, question, selection, settings, limiter)})
    accepted = [row for row in rows if row["status"] == "accepted"]
    payload = {
        "experiment": "P8-B compound citation stability", "model": settings.hcx_model, "rows": rows,
        "summary": {
            "rows": len(rows), "generation_rows": sum(row["representation"] is not None for row in rows),
            "accepted": len(accepted), "citation_exact_copy_rate": round(len(accepted) / max(1, sum(row["representation"] is not None for row in rows)), 3),
            "blocked": sum(row["status"] == "blocked_incomplete_requirement_evidence" for row in rows),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
