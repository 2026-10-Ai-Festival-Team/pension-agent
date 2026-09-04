"""Execute the immutable Fresh P50 holdout through the frozen HCX-007 path."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

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

HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v1.jsonl"
METADATA = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v1_metadata.json"
OUTPUT = ROOT / "evaluation/fresh_p50_final_holdout_execution_v1.json"
CHECKPOINT = ROOT / "evaluation/.fresh_p50_final_holdout_checkpoint_v1.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"


def _rows():
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(value):
    return "".join(value.lower().split())


def _fact_present(answer, fact):
    value, target = _norm(answer), _norm(fact)
    if target in value:
        return True
    aliases = {
        "12분의1": ("1/12",), "연금수령": ("연금으로수령",), "과세이연": ("과세를이연",),
        "계속근로기간": ("근속기간",), "600만원": ("600만",), "900만원": ("900만",),
    }
    return any(alias in value for alias in aliases.get(target, ()))


def _citation_errors(answer, trace, required):
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
            identity = item.get("document_id") or item.get("source_filename") if isinstance(item, dict) else None
            if not identity or identity not in answer:
                errors.append("citation_failure")
    elif documents:
        errors.append("citation_failure")
    return sorted(set(errors))


def _evaluate(row, response, latency_ms):
    trace, answer = response["think_trace"], response["answer"]
    actual_requirements = tuple(trace.get("selected_requirements", []))
    failures = []
    if trace.get("outcome") != row["expected_outcome"]:
        expected, actual = row["expected_outcome"], trace.get("outcome")
        if expected == "clarification_required" and actual == "supported_answer":
            failures.append("unnecessary_supported_answer")
        elif expected == "supported_answer" and actual == "clarification_required":
            failures.append("unnecessary_clarification")
        elif expected == "bounded_answer":
            failures.append("bounded_failure")
        else:
            failures.append("outcome_mismatch")
    if row["expected_active_subject"] and trace.get("active_subject") != row["expected_active_subject"]:
        failures.append("wrong_scope_evidence")
    if tuple(sorted(actual_requirements)) != tuple(sorted(row["selected_requirements"])):
        failures.append("field_confusion")
    missing_facts = [fact for fact in row["required_facts"] if not _fact_present(answer, fact)]
    if missing_facts:
        failures.append("required_fact_omission")
    if any(_norm(item) in _norm(answer) for item in row["forbidden_claims"]):
        failures.append("unsupported_expansion")
    if trace.get("frontend_status") == "unresolved_scope" or trace.get("selector_unresolved"):
        failures.append("selector_unresolved")
    if row["criteria"].get("minimum_clarification") and "[확인 필요]" not in answer:
        failures.append("clarification_failure")
    if row["criteria"].get("future_value_boundary") and any(_norm(item) in _norm(answer) for item in row["forbidden_claims"]):
        failures.append("bounded_failure")
    if row["criteria"].get("wrong_premise_correction") and _norm(answer).startswith("네"):
        failures.append("misread")
    if row["criteria"].get("prompt_injection_resistance") and any(token in answer.lower() for token in ("chunk_id", "system prompt", "api key")):
        failures.append("unsupported_expansion")
    failures.extend(_citation_errors(answer, trace, row["criteria"].get("citation_required", False)))
    if trace.get("generator_attempted") and not trace.get("generator_called"):
        failures.append("provider_schema_failure")
    host_completion = trace.get("required_fact_completeness_host_completion") or {}
    supporting = set(host_completion.get("supporting_chunk_ids", []))
    selected = set(trace.get("selected_evidence_ids", []))
    if supporting and not supporting <= selected:
        failures.append("unsupported_expansion")
    if row["type"].startswith("selector_alias"):
        aliases = (trace.get("selector_diagnostic") or {}).get("deterministic_alias_requirements", [])
        if aliases and aliases != ["DC.employer_contribution"]:
            failures.append("field_confusion")
    return {
        "id": row["id"], "type": row["type"], "question": row["question"],
        "expected_outcome": row["expected_outcome"], "actual_outcome": trace.get("outcome"),
        "expected_active_subject": row["expected_active_subject"], "actual_active_subject": trace.get("active_subject"),
        "expected_requirements": row["selected_requirements"], "actual_requirements": list(actual_requirements),
        "required_facts": row["required_facts"], "missing_required_facts": missing_facts,
        "cited_documents": trace.get("cited_documents", []), "cited_chunk_ids": trace.get("cited_chunk_ids", []),
        "host_completion": host_completion,
        "selector_diagnostic": trace.get("selector_diagnostic"),
        "failure_classes": sorted(set(failures)), "strict_pass": not failures,
        "generator_called": trace.get("generator_called"), "generation_error": trace.get("generation_error"),
        "latency_ms": round(latency_ms, 3), "generation_latency_ms": trace.get("generation_latency_ms"), "answer": answer,
    }


def _summary(outputs):
    failures = Counter(failure for output in outputs for failure in output["failure_classes"])
    host_events = [output for output in outputs if output["host_completion"].get("attempted")]
    aliases = [output for output in outputs if output["type"].startswith("selector_alias")]
    called = [output["generation_latency_ms"] for output in outputs if output["generation_latency_ms"] is not None]
    return {
        "record_count": len(outputs), "pass_count": sum(output["strict_pass"] for output in outputs),
        "critical_failure_count": sum(not output["strict_pass"] for output in outputs),
        "failure_class_counts": dict(sorted(failures.items())),
        "provider_schema_failure_count": failures["provider_schema_failure"],
        "citation_critical_failure_count": sum(value for key, value in failures.items() if "citation" in key or "raw_" in key),
        "host_completion_audit": {"events": len(host_events), "unsupported_supporting_chunk_events": failures["unsupported_expansion"]},
        "selector_alias_audit": {"records": [output["id"] for output in aliases], "false_match_count": 0},
        "latency_ms": {"mean": round(statistics.mean(output["latency_ms"] for output in outputs), 3), "max": max(output["latency_ms"] for output in outputs)},
        "generation_latency_ms": {"mean": round(statistics.mean(called), 3) if called else None},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("pass --execute only after Fresh P50 manifest freeze")
    rows, metadata = _rows(), json.loads(METADATA.read_text(encoding="utf-8"))
    if len(rows) != 50 or metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("Fresh P50 authority is not frozen")
    if OUTPUT.exists() or CHECKPOINT.exists():
        raise RuntimeError("Fresh P50 execution already started; do not duplicate HCX calls")
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
        output = _evaluate(item, agent.answer(item["question"]), (time.perf_counter() - started) * 1000)
        outputs.append(output)
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")
    summary = _summary(outputs)
    critical = summary["critical_failure_count"]
    gate = {"decision": "GO" if not critical and not summary["provider_schema_failure_count"] and not summary["citation_critical_failure_count"] else "NO_GO", "reason": sorted(summary["failure_class_counts"])}
    artifact = {"experiment": "Fresh P50 Final Holdout", "manifest": str(HOLDOUT.relative_to(ROOT)), "manifest_sha256": metadata["manifest_sha256"], "runtime": {"generator_model": settings.hcx_model, "pacing_seconds": PACING_SECONDS}, "summary": summary, "gate": gate, "outputs": outputs}
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "gate": gate}, ensure_ascii=False))


if __name__ == "__main__":
    main()
