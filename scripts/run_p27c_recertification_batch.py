"""P27-C Full-40을 세션 제한 없이 순차 배치로 실행한다.

Agent 조합과 HCX 설정을 바꾸지 않고, 각 배치가 끝날 때 결과를 checkpoint로 저장한다.
두 배치는 호출을 병렬화하지 않으며 동일한 6초 hard pacing을 사용한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.generation.factory import build_answer_generator
from src.orchestration.retrieval_service import build_frozen_retriever


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--label-output", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P27-C는 실제 HCX 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-007":
        raise SystemExit("P27-C에는 GENERATOR_BACKEND=hcx 및 HCX_MODEL=HCX-007이 필요합니다.")
    settings = replace(settings, hcx_min_interval_seconds=6.0)
    questions = load_questions(args.questions)[args.start : args.end]
    if not questions:
        raise SystemExit("선택된 P27-C 배치에 질문이 없습니다.")

    agent = P26CandidateAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=build_answer_generator(settings),
    )
    rows = evaluate_agent(TestClient(create_app(agent)), questions)
    attempts = _attempts(rows)
    payload = {
        "experiment": "P27-C output-contract recertification batch",
        "hcx_called": True,
        "question_range": [args.start, args.end],
        "model": settings.hcx_model,
        "settings": {
            "minimum_interval_seconds": settings.hcx_min_interval_seconds,
            "pacing_guard_seconds": settings.hcx_pacing_guard_seconds,
            "max_retries": settings.max_retries,
        },
        "provider_summary": summarize_provider_attempts(attempts),
        "rows": rows,
        "attempt_telemetry": attempts,
    }
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.label_output.parent.mkdir(parents=True, exist_ok=True)
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
                        "route": row.get("route"),
                        "evidence_sufficient": row.get("evidence_sufficient"),
                        "generator_called": row.get("generator_called"),
                        "citation_valid": row.get("citation_valid"),
                        "cited_chunk_ids": row.get("cited_chunk_ids", []),
                        "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(json.dumps({"questions": len(rows), "provider_summary": payload["provider_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
