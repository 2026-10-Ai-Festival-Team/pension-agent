"""Execute the once-frozen Fresh P50 v2 holdout through HCX-007."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import re

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v2.jsonl"
METADATA = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v2_metadata.json"
OUTPUT = ROOT / "evaluation/fresh_p50_final_holdout_execution_v2.json"
CHECKPOINT = ROOT / "evaluation/.fresh_p50_final_holdout_checkpoint_v2.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"


def _rows():
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(value: str) -> str:
    return "".join(value.lower().split())


def _fact_present(answer: str, fact: str) -> bool:
    value, target = _norm(answer), _norm(fact)
    if target in value:
        return True
    aliases = {
        "12분의1": ("1/12",),
        "연금수령": ("연금으로수령",),
        "과세이연": ("과세를이연",),
        # Exact negation-preserving lexical equivalence for the canonical
        # non-exemption fact; this is not global fuzzy matching.
        "면세": ("비과세",),
        "계속근로기간": ("근속기간",),
        "1000만원": ("1천만원",),
    }
    return any(alias in value for alias in aliases.get(target, ()))


def _citation_errors(answer: str, trace: dict, required: bool) -> list[str]:
    documents, cited = trace.get("cited_documents", []), trace.get("cited_chunk_ids", [])
    errors = []
    if any(chunk_id in answer for chunk_id in cited):
        errors.append("raw_chunk_id_exposure")
    if any(isinstance(item, dict) and item.get("source_id") in answer for item in documents):
        errors.append("raw_source_id_exposure")
    if required:
        if not documents:
            errors.append("citation_failure")
        for item in documents:
            if not isinstance(item, dict):
                errors.append("citation_failure")
                continue
            identity = item.get("document_id") or item.get("source_filename")
            if not identity or identity not in answer:
                errors.append("citation_failure")
    elif documents:
        errors.append("citation_failure")
    return sorted(set(errors))


def _evaluate(row: dict, response: dict, latency_ms: float) -> dict:
    trace, answer = response["think_trace"], response["answer"]
    actual_requirements = tuple(trace.get("selected_requirements", []))
    failures: list[str] = []
    expected_outcome, actual_outcome = row["expected_outcome"], trace.get("outcome")
    if actual_outcome != expected_outcome:
        failures.append({
            ("supported_answer", "clarification_required"): "unnecessary_clarification",
            ("clarification_required", "supported_answer"): "unnecessary_supported_answer",
            ("bounded_answer", actual_outcome): "bounded_failure",
        }.get((expected_outcome, actual_outcome), "outcome_mismatch"))
    expected_subject = row.get("expected_active_subject")
    if expected_subject and trace.get("active_subject") != expected_subject:
        failures.append("wrong_scope_evidence")
    expected_requirements = tuple(row.get("selected_requirements", ()))
    if expected_requirements and tuple(sorted(actual_requirements)) != tuple(sorted(expected_requirements)):
        failures.append("field_confusion")
    missing = [fact for fact in row["required_facts"] if not _fact_present(answer, fact)]
    if expected_outcome == "supported_answer" and missing:
        failures.append("required_fact_omission")
    if trace.get("frontend_status") == "unresolved_scope" or trace.get("selector_unresolved"):
        failures.append("selector_unresolved")
    if row.get("criteria", {}).get("minimum_clarification") and "[확인 필요]" not in answer:
        failures.append("clarification_failure")
    if row.get("criteria", {}).get("prompt_injection_resistance") and any(token in answer.lower() for token in ("chunk_id", "system prompt", "api key", "시스템 지시문")):
        failures.append("prompt_injection_failure")
    failures.extend(_citation_errors(answer, trace, row.get("criteria", {}).get("citation_required", False)))
    if trace.get("generator_attempted") and not trace.get("generator_called"):
        failures.append("provider_schema_failure")
    host_completion = trace.get("required_fact_completeness_host_completion") or {}
    supporting = set(host_completion.get("supporting_chunk_ids", []))
    selected = set(trace.get("selected_evidence_ids", []))
    if supporting and not supporting <= selected:
        failures.append("unsupported_expansion")
    result = {
        "id": row["id"], "type": row["type"], "question": row["question"],
        "expected_outcome": expected_outcome, "actual_outcome": actual_outcome,
        "expected_active_subject": expected_subject, "actual_active_subject": trace.get("active_subject"),
        "expected_requirements": list(expected_requirements), "actual_requirements": list(actual_requirements),
        "required_facts": row["required_facts"], "missing_required_facts": missing,
        "cited_documents": trace.get("cited_documents", []), "cited_chunk_ids": trace.get("cited_chunk_ids", []),
        "host_completion": host_completion, "selector_diagnostic": trace.get("selector_diagnostic"),
        "failure_classes": sorted(set(failures)), "strict_pass": not failures,
        "generator_called": trace.get("generator_called"), "generation_error": trace.get("generation_error"),
        "latency_ms": round(latency_ms, 3), "generation_latency_ms": trace.get("generation_latency_ms"), "answer": answer,
    }
    body = answer.split("[답변]", 1)[-1].split("[근거]", 1)[0].strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", body) if part.strip()]
    normal_sentences = [re.sub(r"\s+", "", sentence) for sentence in sentences]
    supported_style = expected_outcome != "supported_answer" or (
        len(sentences) >= 2 and len(normal_sentences) == len(set(normal_sentences))
    )
    result["evaluation_axes"] = {
        "correctness": not any(value in failures for value in ("field_confusion", "outcome_mismatch", "misread")),
        "evidence_completeness": "required_fact_omission" not in failures,
        "requirement_coverage": not any(value in failures for value in ("field_confusion", "selector_unresolved", "required_fact_omission")),
        "grounding_hallucination": "unsupported_expansion" not in failures,
        "reasoning_consistency": "outcome_mismatch" not in failures,
        "safety_reliability": not any(value in failures for value in ("prompt_injection_failure", "provider_schema_failure")),
        "information_limit_handling": not any(value in failures for value in ("bounded_failure", "clarification_failure", "unnecessary_clarification")),
        "citation_document_display": not any("citation" in value or value.startswith("raw_") for value in failures),
    }
    result["style_audit"] = {
        "direct_answer_present": bool(body),
        "explanation_present": expected_outcome != "supported_answer" or len(sentences) >= 2,
        "semantic_explanation": supported_style,
        "repetitive_content": len(normal_sentences) != len(set(normal_sentences)),
    }
    return result


def _summary(outputs: list[dict]) -> dict:
    failures = Counter(item for output in outputs for item in output["failure_classes"])
    called = [output["generation_latency_ms"] for output in outputs if output["generation_latency_ms"] is not None]
    host_events = [output for output in outputs if output["host_completion"].get("attempted")]
    return {
        "record_count": len(outputs),
        "pass_count": sum(output["strict_pass"] for output in outputs),
        "critical_failure_count": sum(not output["strict_pass"] for output in outputs),
        "failure_class_counts": dict(sorted(failures.items())),
        "provider_schema_failure_count": failures["provider_schema_failure"],
        "citation_critical_failure_count": sum(value for key, value in failures.items() if "citation" in key or "raw_" in key),
        "unsupported_hallucination_count": failures["unsupported_expansion"],
        "required_fact_omission_count": failures["required_fact_omission"],
        "information_limit_outcome_error_count": failures["bounded_failure"],
        "prompt_injection_critical_failure_count": failures["prompt_injection_failure"],
        "host_completion_audit": {"events": len(host_events), "unsupported_supporting_chunk_events": failures["unsupported_expansion"]},
        "latency_ms": {"mean": round(statistics.mean(output["latency_ms"] for output in outputs), 3), "max": max(output["latency_ms"] for output in outputs)},
        "generation_latency_ms": {"mean": round(statistics.mean(called), 3) if called else None},
    }


def main():
    global HOLDOUT, METADATA, OUTPUT, CHECKPOINT
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--regression-revision", type=int, default=0)
    parser.add_argument("--finalize-existing-regression", action="store_true")
    parser.add_argument("--holdout-version", type=int, choices=(2, 3, 4), default=2)
    args = parser.parse_args()
    if args.holdout_version == 3:
        HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3.jsonl"
        METADATA = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3_metadata.json"
        OUTPUT = ROOT / "evaluation/fresh_p50_final_holdout_execution_v3.json"
        CHECKPOINT = ROOT / "evaluation/.fresh_p50_final_holdout_checkpoint_v3.jsonl"
    elif args.holdout_version == 4:
        HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v4.jsonl"
        METADATA = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v4_metadata.json"
        OUTPUT = ROOT / "evaluation/fresh_p50_final_holdout_execution_v4.json"
        CHECKPOINT = ROOT / "evaluation/.fresh_p50_final_holdout_checkpoint_v4.jsonl"
    if not args.execute and not args.finalize_existing_regression:
        parser.error("pass --execute only after the v2 manifest is frozen")
    rows, metadata = _rows(), json.loads(METADATA.read_text(encoding="utf-8"))
    if len(rows) != 50 or metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx") or metadata.get("preflight_decision") != "PASS":
        raise RuntimeError("Fresh P50 v2 authority is not frozen and preflight-PASS")
    if args.regression_revision < 0:
        parser.error("regression revision must be non-negative")
    artifact_path = OUTPUT if not args.regression_revision else ROOT / f"evaluation/fresh_p50_v2_regression_execution_v{args.regression_revision}.json"
    checkpoint = CHECKPOINT if not args.regression_revision else ROOT / f"evaluation/.fresh_p50_v2_regression_checkpoint_v{args.regression_revision}.jsonl"
    if args.finalize_existing_regression:
        if not args.regression_revision or artifact_path.exists() or not checkpoint.exists():
            raise RuntimeError("only an unfinished positive regression revision can be finalized")
        outputs = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(outputs) != len(rows):
            raise RuntimeError("regression checkpoint is incomplete; never synthesize missing HCX outputs")
    elif artifact_path.exists() or checkpoint.exists():
        raise RuntimeError("Fresh P50 v2 execution already started; duplicate HCX calls are prohibited")
    else:
        settings = _settings()
        limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
        agent = DirectRequirementE2EAgent(
            scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
            preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
            generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
        )
        outputs = []
        for item in rows:
            started = time.perf_counter()
            record_output = _evaluate(item, agent.answer(item["question"]), (time.perf_counter() - started) * 1000)
            outputs.append(record_output)
            with checkpoint.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record_output, ensure_ascii=False) + "\n")
    summary = _summary(outputs)
    gate = {
        "decision": "GO" if not summary["critical_failure_count"] else "NO_GO",
        "reason": sorted(summary["failure_class_counts"]),
    }
    artifact = {
        "experiment": "Fresh P50 v2 regression" if args.regression_revision else "Fresh P50 Final Holdout v2", "manifest": str(HOLDOUT.relative_to(ROOT)),
        "manifest_sha256": metadata["manifest_sha256"],
        "runtime": {"generator_model": _settings().hcx_model, "pacing_seconds": PACING_SECONDS},
        "summary": summary, "gate": gate, "outputs": outputs,
    }
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "gate": gate}, ensure_ascii=False))


if __name__ == "__main__":
    main()
