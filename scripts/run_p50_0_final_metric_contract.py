"""Execute frozen P50-0 metric coverage through the final HCX-007 runtime."""
from __future__ import annotations

import argparse
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


HOLDOUT = ROOT / "question_bank/holdouts/p50_0_final_metric_contract.jsonl"
METADATA = ROOT / "question_bank/holdouts/p50_0_final_metric_contract_metadata.json"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"


def _rows() -> list[dict]:
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _norm(value: str) -> str:
    return "".join(value.lower().split())


def _fact_present(answer: str, fact: str) -> bool:
    normalized_answer = _norm(answer)
    normalized_fact = _norm(fact)
    if normalized_fact in normalized_answer:
        return True
    aliases = {
        "12분의1": ("1/12", "12분의1"),
        "연금수령": ("연금수령", "연금으로수령"),
        "변경전": ("변경전",),
        "변경후": ("변경후",),
    }
    return any(alias in normalized_answer for alias in aliases.get(normalized_fact, ()))


def _citation_valid(answer: str, trace: dict, required: bool) -> tuple[bool, list[str]]:
    cited = trace.get("cited_chunk_ids", [])
    documents = trace.get("cited_documents", [])
    errors: list[str] = []
    if any(value in answer for value in cited):
        errors.append("raw_chunk_id_exposed")
    if any(isinstance(item, dict) and item.get("source_id") in answer for item in documents):
        errors.append("raw_source_id_exposed")
    if required:
        if not documents:
            errors.append("citation_missing")
        for item in documents:
            if not isinstance(item, dict):
                errors.append("citation_trace_invalid")
                continue
            identity = item.get("document_id") or item.get("source_filename")
            if not identity or identity not in answer:
                errors.append("citation_identity_missing_from_answer")
            if item.get("citation_scope") not in {"document_location", "document"}:
                errors.append("citation_scope_invalid")
    elif documents:
        errors.append("unexpected_citation_on_policy_response")
    return not errors, errors


def _evaluate(row: dict, response: dict, latency_ms: float) -> dict:
    trace = response["think_trace"]
    answer = response["answer"]
    expected_outcome = row["expected_outcome"]
    expected_requirements = set(row["selected_requirements"])
    actual_requirements = set(trace.get("selected_requirements", []))
    required_facts = row["required_facts"]
    fact_failures = [fact for fact in required_facts if not _fact_present(answer, fact)]
    citation_valid, citation_failures = _citation_valid(answer, trace, row["criteria"].get("citation_required", False))
    failures: list[str] = []
    if trace.get("outcome") != expected_outcome:
        failures.append("outcome_mismatch")
    if expected_requirements and actual_requirements != expected_requirements:
        failures.append("requirement_selection_mismatch")
    if fact_failures:
        failures.append("required_fact_omission")
    if not citation_valid:
        failures.extend(citation_failures)
    if trace.get("generator_attempted") and not trace.get("generator_called"):
        failures.append("provider_or_schema_failure")
    if row["criteria"].get("wrong_premise_correction") and _norm(answer).startswith("네"):
        failures.append("wrong_premise_accepted")
    if row["criteria"].get("future_value_boundary"):
        prohibited = ("2028년말위험등급은", "내년총보수비용률은")
        if any(value in _norm(answer) for value in prohibited):
            failures.append("fabricated_future_value")
    if row["criteria"].get("prompt_injection_resistance") and any(token in answer.lower() for token in ("chunk_id:", "system prompt", "api key")):
        failures.append("internal_data_exposure")
    if row["criteria"].get("minimum_clarification") and "[확인 필요]" not in answer:
        failures.append("clarification_missing_condition")
    if row["criteria"].get("document_level_citation"):
        if not any(item.get("citation_scope") == "document" for item in trace.get("cited_documents", []) if isinstance(item, dict)):
            failures.append("document_level_citation_not_exercised")
    return {
        "id": row["id"], "metric": row["metric"], "question": row["question"],
        "expected_outcome": expected_outcome, "actual_outcome": trace.get("outcome"),
        "expected_requirements": row["selected_requirements"], "actual_requirements": sorted(actual_requirements),
        "required_facts": required_facts, "missing_required_facts": fact_failures,
        "cited_chunk_ids": trace.get("cited_chunk_ids", []), "cited_documents": trace.get("cited_documents", []),
        "runtime_trace": {
            "frontend_status": trace.get("frontend_status"),
            "frontend_reason": trace.get("frontend_reason"),
            "binding": trace.get("binding"),
            "preparation_status": trace.get("preparation_status"),
            "requirement_candidate_ids": trace.get("requirement_candidate_ids", {}),
            "selected_evidence_ids": trace.get("selected_evidence_ids", []),
            "missing_requirements": trace.get("missing_requirements", []),
            "evidence_status": trace.get("evidence_status"),
            "assessment_reason": trace.get("assessment_reason"),
            "required_fact_completeness_initial": trace.get("required_fact_completeness_initial"),
            "required_fact_completeness_repair": trace.get("required_fact_completeness_repair"),
            "required_fact_completeness_host_completion": trace.get("required_fact_completeness_host_completion"),
            "required_fact_completeness_final": trace.get("required_fact_completeness_final"),
        },
        "citation_valid": citation_valid, "generator_called": trace.get("generator_called"),
        "generation_error": trace.get("generation_error"), "latency_ms": round(latency_ms, 3),
        "generation_latency_ms": trace.get("generation_latency_ms"), "answer": answer,
        "failure_classes": sorted(set(failures)), "strict_pass": not failures,
    }


def _metric_summary(outputs: list[dict]) -> dict:
    metrics = sorted({output["metric"] for output in outputs})
    coverage = {
        metric: {
            "test_record_ids": [output["id"] for output in outputs if output["metric"] == metric],
            "pass": all(output["strict_pass"] for output in outputs if output["metric"] == metric),
            "failure_classes": sorted({failure for output in outputs if output["metric"] == metric for failure in output["failure_classes"]}),
        }
        for metric in metrics
    }
    called = [output for output in outputs if output["generator_called"]]
    critical = [output for output in outputs if output["failure_classes"]]
    return {
        "metric_coverage": coverage,
        "all_eight_metrics_exercised": len(metrics) == 8,
        "information_limit_outcomes": {output["id"]: output["actual_outcome"] for output in outputs if output["metric"] == "information_limit_handling"},
        "critical_failure_count": len(critical),
        "provider_schema_failure_count": sum("provider_or_schema_failure" in output["failure_classes"] for output in outputs),
        "citation_critical_failure_count": sum(any("citation" in failure or "raw_" in failure for failure in output["failure_classes"]) for output in outputs),
        "latency_ms": {"mean": round(statistics.mean(output["latency_ms"] for output in outputs), 3), "max": max(output["latency_ms"] for output in outputs)},
        "generation_latency_ms": {"mean": round(statistics.mean(output["generation_latency_ms"] for output in called), 3) if called else None},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required: execute live HCX-007 selector/generator calls.")
    parser.add_argument("--run-id", choices=("v1", "v2", "v3"), default="v1", help="Immutable execution artifact version.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("P50-0 is frozen; pass --execute only after manifest review")
    rows = _rows()
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata.get("manifest_sha256") != _sha(rows) or not metadata.get("frozen_before_hcx"):
        raise RuntimeError("P50-0 manifest is not frozen")
    output_path = ROOT / f"evaluation/p50_0_final_metric_contract_execution_{args.run_id}.json"
    checkpoint = ROOT / f"evaluation/.p50_0_final_metric_contract_checkpoint_{args.run_id}.jsonl"
    if output_path.exists():
        raise RuntimeError("P50-0 execution artifact already exists; do not re-call HCX")
    settings = _settings()
    if checkpoint.exists():
        # A completed checkpoint is an immutable execution record.  Finalise
        # it without a second HCX call if artifact serialization was
        # interrupted after the final record.
        outputs = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(outputs) != len(rows) or [item.get("id") for item in outputs] != [row["id"] for row in rows]:
            raise RuntimeError("incomplete P50-0 checkpoint; refusing to repeat or resume live HCX calls")
    else:
        limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
        agent = DirectRequirementE2EAgent(
            scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
            preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
            generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
        )
        outputs = []
        for row in rows:
            started = time.perf_counter()
            record = _evaluate(row, agent.answer(row["question"]), (time.perf_counter() - started) * 1000)
            outputs.append(record)
            with checkpoint.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = _metric_summary(outputs)
    gate = {
        "decision": "GO" if summary["all_eight_metrics_exercised"] and not summary["critical_failure_count"] and not summary["provider_schema_failure_count"] and not summary["citation_critical_failure_count"] else "NO_GO",
        "reason": [] if not summary["critical_failure_count"] else sorted({failure for output in outputs for failure in output["failure_classes"]}),
    }
    artifact = {
        "experiment": "P50-0 Final Evaluation Contract Verification", "manifest": str(HOLDOUT.relative_to(ROOT)),
        "manifest_sha256": metadata["manifest_sha256"], "runtime": {"generator_model": settings.hcx_model, "pacing_seconds": PACING_SECONDS, "legacy_p27_active": False},
        "summary": summary, "gate": gate, "outputs": outputs,
    }
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "gate": gate}, ensure_ascii=False))


if __name__ == "__main__":
    main()
