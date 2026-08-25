"""Frozen P32 holdout을 P31 v2 코드 변경 없이 실행한다."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_p26_candidate_hcx import _attempts
from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.provider_stability import summarize_provider_attempts
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p32_holdout_manifest.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--raw-output", type=Path, default=ROOT / "data/diagnostics/p32_holdout_raw.json")
    parser.add_argument("--execution-output", type=Path, default=ROOT / "evaluation/p32_holdout_execution.jsonl")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P32는 실제 HCX 비용이 발생합니다. --execute가 필요합니다.")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    questions = manifest["questions"]
    denominator = manifest["denominators"]
    if len(questions) != denominator["total"] or sum(q["answerability"] == "answerable" for q in questions) != denominator["answerable"]:
        raise SystemExit("P32 manifest denominator가 동결된 질문 수와 일치하지 않습니다.")
    if sum(q["answerability"] == "unsupported" for q in questions) != denominator["unsupported"]:
        raise SystemExit("P32 unsupported denominator가 일치하지 않습니다.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P32에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    generator = HyperClovaXGenerator(
        config=settings,
        prompt_builder=NativeStructuredOutputPromptBuilder(),
        rate_limiter=GlobalMinIntervalLimiter(settings.hcx_min_interval_seconds, guard_seconds=settings.hcx_pacing_guard_seconds),
    )
    agent = P27DStructuredOutputAgent(retriever=build_frozen_retriever(args.corpus, args.index), generator=generator)
    client = TestClient(create_app(agent))
    rows = []
    started = time.perf_counter()
    for question in questions:
        response = client.get("/answer", params={"question_id": question["question_id"], "question": question["question"], "top_k": 10})
        body = response.json() if response.status_code == 200 else {}
        trace = body.get("think_trace", {})
        diagnostic = trace.get("generation_diagnostic") or {}
        rows.append({
            "question_id": question["question_id"], "question": question["question"], "category": question["category"],
            "answerability": question["answerability"], "expected_policy_behavior": question["expected_policy_behavior"],
            "required_requirements": question["required_requirements"], "critical_facts": question["critical_facts"], "forbidden_claims": question["forbidden_claims"],
            "status_code": response.status_code, "answer": body.get("answer", ""),
            "answer_hash": hashlib.sha256(body.get("answer", "").encode("utf-8")).hexdigest(),
            "route": trace.get("route"), "requirement_plan": trace.get("requirement_plan"),
            "evidence_sufficient": trace.get("evidence_sufficient"), "evidence_reason": trace.get("assessment_reason"),
            "missing_requirement_slots": trace.get("missing_requirement_slots", []), "generator_attempted": trace.get("generator_attempted", False),
            "generator_called": trace.get("generator_called", False), "generation_error": trace.get("generation_error"),
            "citation_valid": bool(trace.get("cited_chunk_ids")) and trace.get("generation_error") is None if trace.get("generator_called") else True,
            "cited_chunk_ids": trace.get("cited_chunk_ids", []), "selected_merged_evidence_ids": trace.get("selected_merged_evidence_ids", []),
            "generation_attempt_history": diagnostic.get("attempt_history", []),
            "semantic_correctness": "pending_manual_review", "requirement_coverage": "pending_manual_review",
            "grounding": "pending_manual_review", "policy_behavior": "pending_manual_review", "strict_useful": "pending_manual_review"
        })
    attempts = _attempts(rows)
    payload = {"experiment":"P32 fresh frozen holdout", "manifest_version":manifest["version"], "model":settings.hcx_model,
        "fixed_conditions":{"p31_v2_code":"unchanged","native_structured_outputs":True,"thinking_effort":"none","minimum_interval_seconds":6.0,"strict_validator":True},
        "duration_ms":round((time.perf_counter()-started)*1000,3), "denominators":denominator,
        "provider_summary":summarize_provider_attempts(attempts), "rows":rows, "attempt_telemetry":attempts}
    args.raw_output.parent.mkdir(parents=True, exist_ok=True); args.execution_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.execution_output.write_text("".join(json.dumps(row, ensure_ascii=False)+"\n" for row in rows), encoding="utf-8")
    print(json.dumps({"questions":len(rows), "provider_summary":payload["provider_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
