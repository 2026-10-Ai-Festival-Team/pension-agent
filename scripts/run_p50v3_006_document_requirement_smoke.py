"""Run the narrow post-adjudication HCX-007 smoke for P50V3-006.

The original immutable P50 v3 record is not re-called: an earlier attempt was
interrupted before it could persist an artifact, so replaying that same holdout
question would violate the no-duplicate-call rule.  The first row is a new
same-contract probe; the next two are positive and unrelated-scope controls.
This script intentionally has an immutable output path to prevent duplicates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_fresh_p50_v2_final_holdout import _evaluate
from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.generation.versioned_generator_prompt import load_generator_prompt
from src.orchestration.retrieval_service import build_frozen_retriever


HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
OUTPUT = ROOT / "evaluation/p50v3_006_document_requirement_smoke_v1.json"
CHECKPOINT = ROOT / "evaluation/.p50v3_006_document_requirement_smoke_checkpoint_v1.jsonl"


def _rows() -> tuple[dict, ...]:
    return (
        {
            "id": "P50V3-006-same-contract-probe",
            "type": "direct",
            "question": "DC 중도인출 때 법정사유를 입증하려면 증빙서류를 준비해야 하나요?",
            "expected_outcome": "supported_answer",
            "expected_active_subject": "DC",
            "selected_requirements": ["DC.early_withdrawal.required_documents"],
            "required_facts": ["증빙서류"],
            "criteria": {"citation_required": True},
        },
        {
            "id": "P50V3-006-positive-document-control",
            "type": "direct",
            "question": "DC형 중도인출을 신청하려면 사유에 맞는 증빙서류를 갖춰야 하나요?",
            "expected_outcome": "supported_answer",
            "expected_active_subject": "DC",
            "selected_requirements": ["DC.early_withdrawal.required_documents"],
            "required_facts": ["증빙서류"],
            "criteria": {"citation_required": True},
        },
        {
            "id": "P50V3-006-negative-irp-scope-control",
            "type": "direct",
            "question": "IRP에서 연금수령 전에 인출할 수 있는 사유는 법정사유로 정해져 있나요?",
            "expected_outcome": "supported_answer",
            "expected_active_subject": "IRP",
            "selected_requirements": ["IRP.early_withdrawal.allowed_reasons"],
            "required_facts": ["법정사유"],
            "criteria": {"citation_required": True},
        },
    )


def _agent() -> DirectRequirementE2EAgent:
    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    return DirectRequirementE2EAgent(
        scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
        preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
        generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
        prompt_contract=load_generator_prompt("generator_prompt_final_v2_1"),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("pass --execute after deterministic document-contract tests pass")
    if OUTPUT.exists():
        raise RuntimeError("smoke artifact already exists; duplicate HCX calls are prohibited")

    prompt = load_generator_prompt("generator_prompt_final_v2_1")
    agent = _agent()
    completed = {
        output["id"]: output
        for line in CHECKPOINT.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for output in (json.loads(line),)
    } if CHECKPOINT.exists() else {}
    rows = _rows()
    unknown_checkpoint_ids = set(completed) - {row["id"] for row in rows}
    if unknown_checkpoint_ids:
        raise RuntimeError(f"unexpected checkpoint IDs: {sorted(unknown_checkpoint_ids)}")
    for row in _rows():
        if row["id"] in completed:
            continue
        started = time.perf_counter()
        output = _evaluate(row, agent.answer(row["question"]), (time.perf_counter() - started) * 1000)
        completed[row["id"]] = output
        with CHECKPOINT.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(output, ensure_ascii=False) + "\n")

    if len(completed) != len(rows):
        raise RuntimeError("smoke checkpoint is incomplete")
    outputs = [completed[row["id"]] for row in rows]

    prohibited = {"required_fact_omission", "unsupported_expansion", "citation_failure", "outcome_mismatch", "field_confusion", "provider_schema_failure"}
    failure_classes = sorted({failure for output in outputs for failure in output["failure_classes"]})
    artifact = {
        "experiment": "P50V3-006 document-requirement targeted smoke",
        "hcx_calls": "actual HCX-007 runtime only for these 3 rows",
        "generator_model": _settings().hcx_model,
        "generator_prompt_id": prompt.prompt_id,
        "generator_prompt_sha256": prompt.prompt_sha256,
        "outputs": outputs,
        "summary": {
            "record_count": len(outputs),
            "pass_count": sum(output["strict_pass"] for output in outputs),
            "failure_classes": failure_classes,
            "host_completion_count": sum(bool(output["host_completion"].get("attempted")) for output in outputs),
            "gate": "GO" if not set(failure_classes) & prohibited and all(output["strict_pass"] for output in outputs) else "NO_GO",
        },
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
