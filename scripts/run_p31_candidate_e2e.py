"""P31 Full-40 single-pass candidate E2E 실행기.

P30의 requirement planner와 product-field boundary를 포함한 현재 candidate
composition을 실제 HCX-007에 한 번만 연결한다. 이 파일은 평가 산출물과
운영 계약을 기록할 뿐 Agent, prompt, retrieval, gate, policy, pacing을 바꾸지
않는다. semantic 판정은 생성된 answer hash를 대상으로 별도 수행한다.
"""

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
from src.evaluation.agent_evaluator import evaluate_agent
from src.evaluation.provider_stability import summarize_provider_attempts
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


P30_TARGETS = ("R-011", "R-034", "R-035", "R-038")
SAFETY_BLOCKS = ("R-019", "R-039", "R-040")


def _operational_summary(rows: list[dict], attempts: list[dict]) -> dict:
    provider = summarize_provider_attempts(attempts)
    diagnostics = [row.get("generation_diagnostic") or {} for row in rows]
    schema_failures = sum(bool(row.get("generation_error")) for row in rows)
    empty_answer = sum(
        "empty_answer" in item.get("response_contract_failures", []) for item in diagnostics
    )
    empty_citation = sum(
        "empty_cited_chunk_ids" in item.get("response_contract_failures", [])
        for item in diagnostics
    )
    citation_failures = sum(
        bool(row.get("generator_attempted"))
        and not row.get("citation_valid")
        and not row.get("generation_error")
        for row in rows
    )
    by_id = {row["question_id"]: row for row in rows}
    return {
        **provider,
        "api_success": sum(row.get("status_code") == 200 for row in rows),
        "question_count": len(rows),
        "generator_attempted": sum(bool(row.get("generator_attempted")) for row in rows),
        "policy_blocked": sum(not row.get("generator_attempted") for row in rows),
        "schema_failure": schema_failures,
        "empty_answer": empty_answer,
        "empty_citation": empty_citation,
        "citation_validator_failure": citation_failures,
        "r019_generator_called": by_id["R-019"].get("generator_called"),
        "r039_safely_blocked": not by_id["R-039"].get("generator_attempted"),
        "r040_safely_blocked": not by_id["R-040"].get("generator_attempted"),
    }


def _markdown(payload: dict) -> str:
    summary = payload["operational_summary"]
    p30 = payload["p30_preflight"]
    targets = {item["question_id"]: item for item in payload["p30_target_preparation"]}
    lines = [
        "# P31: Full-40 Candidate E2E 실행",
        "",
        "P30 requirement planner와 product-field boundary를 포함한 single-pass candidate를 고정 조건으로 실행했다. 이 보고서는 운영·안전 계약만 기록한다. semantic 품질은 새 answer hash를 대상으로 별도 수동 라벨링한다.",
        "",
        "## 고정 조건",
        "",
        "- HCX-007 Native Structured Outputs (`thinking.effort=none`)",
        "- P24-B retrieval/matcher candidate",
        "- P29 provenance/financial answer policy",
        "- P30 requirement planner/product-field boundary",
        "- strict parser, strict citation validator, Fail-Closed",
        "- global HCX request-start interval: 6초 + guard",
        "",
        "## P30 Offline Preflight",
        "",
        f"- shared preparation parity: {p30['shared_preparation_parity']}",
        f"- known false rejection: {len(p30['known_false_rejection'])}",
        f"- known unsafe pass: {len(p30['known_unsafe_pass'])}",
        f"- P15 route/gate regressions: {len(p30['p15_route_gate_regressions'])}",
        "",
        "## 실행 결과",
        "",
        "| 항목 | 결과 |",
        "|---|---:|",
        f"| API 200 | {summary['api_success']}/{summary['question_count']} |",
        f"| HCX 호출 대상 | {summary['generator_attempted']} |",
        f"| HTTP 429 / 5xx / timeout | {summary['http_429']} / {summary['http_5xx']} / {summary['timeout']} |",
        f"| Retry exhaustion | {summary['retry_exhaustion']} |",
        f"| JSON/schema failure | {summary['schema_failure']} |",
        f"| Empty answer / citation | {summary['empty_answer']} / {summary['empty_citation']} |",
        f"| Citation validator failure | {summary['citation_validator_failure']} |",
        f"| 최소 request-start 간격(ms) | {summary['min_request_start_delta_ms']} |",
        f"| R-019 HCX 호출 | {summary['r019_generator_called']} |",
        f"| R-039 / R-040 안전 차단 | {summary['r039_safely_blocked']} / {summary['r040_safely_blocked']} |",
        "",
        "## P30 Target Preparation",
        "",
        "| ID | Route | Gate | Requirement slots | Selected evidence |",
        "|---|---|---|---:|---:|",
    ]
    for question_id in P30_TARGETS:
        row = targets[question_id]
        slots = (row.get("requirement_plan") or {}).get("slots", [])
        lines.append(
            f"| {question_id} | {row.get('route')} | {row.get('evidence_reason')} | "
            f"{len(slots)} | {len(row.get('selected_merged_evidence_ids', []))} |"
        )
    lines.extend(
        [
            "",
            "## 다음 단계",
            "",
            "`evaluation/p31_candidate_execution.jsonl`의 `answer_hash`별로 semantic correctness, requirement coverage, grounding, policy behavior, strict useful을 새로 라벨링한다. 이 실행만으로 Strict E2E Useful 또는 production 승격을 선언하지 않는다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="실제 HCX 비용이 발생한다.")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument(
        "--p30-preflight",
        type=Path,
        default=ROOT / "evaluation/p30_requirement_boundary_offline.json",
    )
    parser.add_argument(
        "--raw-output",
        type=Path,
        default=ROOT / "data/diagnostics/p31_candidate_e2e_raw.json",
    )
    parser.add_argument(
        "--label-output",
        type=Path,
        default=ROOT / "evaluation/p31_candidate_execution.jsonl",
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/p31_full40_candidate_e2e.md"
    )
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P31은 실제 HCX 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")

    p30 = json.loads(args.p30_preflight.read_text(encoding="utf-8"))
    if not p30.get("go"):
        raise SystemExit("P30 offline preflight가 Go가 아니므로 P31 HCX 실행을 차단했습니다.")
    if p30.get("shared_preparation_parity") != "40/40":
        raise SystemExit("P30 shared preparation parity가 40/40이 아니므로 P31 실행을 차단했습니다.")
    if p30.get("known_false_rejection") or p30.get("known_unsafe_pass"):
        raise SystemExit("P30 preflight에 known gate issue가 있어 P31 실행을 차단했습니다.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P31에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    questions = load_questions(args.questions)
    if len(questions) != 40:
        raise SystemExit(f"P31은 40개 평가 질문이 필요합니다. 현재: {len(questions)}")

    limiter = GlobalMinIntervalLimiter(
        settings.hcx_min_interval_seconds,
        guard_seconds=settings.hcx_pacing_guard_seconds,
    )
    generator = HyperClovaXGenerator(
        config=settings,
        prompt_builder=NativeStructuredOutputPromptBuilder(),
        rate_limiter=limiter,
    )
    agent = P27DStructuredOutputAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=generator,
    )
    started = time.perf_counter()
    rows = evaluate_agent(TestClient(create_app(agent)), questions)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    attempts = _attempts(rows)
    summary = _operational_summary(rows, attempts)
    target_rows = [row for row in rows if row["question_id"] in P30_TARGETS]
    payload = {
        "experiment": "P31 Full-40 P30 candidate E2E",
        "hcx_called": True,
        "model": settings.hcx_model,
        "fixed_conditions": {
            "p24b_retrieval_matcher": "candidate",
            "p29_financial_policy": "enabled",
            "p30_requirement_planner": "candidate",
            "p30_product_field_boundary": "candidate",
            "native_structured_outputs": True,
            "thinking_effort": "none",
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "pacing_guard_seconds": settings.hcx_pacing_guard_seconds,
            "max_retries": settings.max_retries,
            "parser": "strict_fail_closed",
            "citation_validator": "strict_subset",
        },
        "duration_ms": duration_ms,
        "p30_preflight": p30,
        "operational_summary": summary,
        "p30_target_preparation": target_rows,
        "rows": rows,
        "attempt_telemetry": attempts,
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.label_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.label_output.open("w", encoding="utf-8") as output:
        for row, question in zip(rows, questions):
            output.write(
                json.dumps(
                    {
                        "question_id": row["question_id"],
                        "question": question.question,
                        "answer": row["answer"],
                        "answer_hash": hashlib.sha256(row["answer"].encode("utf-8")).hexdigest(),
                        "answerable": question.answerable,
                        "route": row.get("route"),
                        "requirement_plan": row.get("requirement_plan"),
                        "evidence_sufficient": row.get("evidence_sufficient"),
                        "evidence_reason": row.get("evidence_reason"),
                        "missing_requirement_slots": row.get("missing_requirement_slots", []),
                        "generator_attempted": row.get("generator_attempted"),
                        "generator_called": row.get("generator_called"),
                        "citation_valid": row.get("citation_valid"),
                        "cited_chunk_ids": row.get("cited_chunk_ids", []),
                        "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
                        "semantic_correctness": "pending_manual_review",
                        "requirement_coverage": "pending_manual_review",
                        "grounding": "pending_manual_review",
                        "policy_behavior": "pending_manual_review",
                        "strict_useful": "pending_manual_review",
                        "failure_reason": None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    args.report.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({"operational_summary": summary, "duration_ms": duration_ms}, ensure_ascii=False))
    if summary["api_success"] != 40:
        raise SystemExit("P31 API 성공이 40/40이 아닙니다. 결과는 진단용으로 보존했습니다.")


if __name__ == "__main__":
    main()
