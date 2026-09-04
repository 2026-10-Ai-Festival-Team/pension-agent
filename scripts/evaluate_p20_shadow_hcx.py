"""P20: P19 shared preparation을 실제 HCX Shadow E2E로 한 번 평가한다."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import create_app
from src.config.generation import GenerationSettings
from src.evaluation.agent_evaluator import evaluate_agent
from src.evaluation.retrieval_dataset import load_questions
from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.factory import build_answer_generator
from src.orchestration.retrieval_service import build_frozen_retriever
from evaluate_p16_shadow_hcx import _operational_summary


PARITY_FIELDS = (
    "route",
    "extracted_entities",
    "requirement_plan",
    "base_retrieved_chunk_ids",
    "candidate_chunk_ids",
    "evidence_sufficient",
    "gate_decision",
    "selected_merged_evidence_ids",
    "hcx_would_be_invoked",
)


def _p19_states(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("static_question_id_cases_used_for_preparation"):
        raise ValueError("P20 requires the dynamic P19 shared-preparation artifact")
    states = {}
    for row in payload["rows"]:
        states[row["question_id"]] = {
            "route": row["route"],
            "extracted_entities": row["extracted_entities"],
            "requirement_plan": row["requirement_plan"],
            "base_retrieved_chunk_ids": row["base_retrieved_chunk_ids"],
            "candidate_chunk_ids": row["candidate_chunk_ids"],
            "evidence_sufficient": row["evidence_sufficient"],
            "gate_decision": row["gate_decision"],
            "selected_merged_evidence_ids": row["selected_merged_evidence_ids"],
            "hcx_would_be_invoked": row["hcx_would_be_invoked"],
        }
    return states


def _p20_state(row: dict) -> dict:
    return {
        "route": row.get("route"),
        "extracted_entities": row.get("extracted_entities"),
        "requirement_plan": row.get("requirement_plan"),
        "base_retrieved_chunk_ids": row.get("base_retrieved_chunk_ids", []),
        "candidate_chunk_ids": row.get("candidate_chunk_ids", []),
        "evidence_sufficient": row.get("evidence_sufficient"),
        "gate_decision": row.get("evidence_reason"),
        "selected_merged_evidence_ids": row.get("selected_merged_evidence_ids", []),
        "hcx_would_be_invoked": row.get("generator_attempted", False),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--p19-preparation", type=Path, default=ROOT / "data/diagnostics/p18_shared_shadow_preparation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/diagnostics/p20_shadow_hcx.json")
    parser.add_argument("--preparation-output", type=Path, default=ROOT / "data/diagnostics/p20_shadow_preparation.json")
    parser.add_argument("--execute", action="store_true", help="실제 HCX를 호출한다.")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("P20은 실제 비용이 발생합니다. 실행하려면 --execute를 지정하세요.")

    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend != "hcx" or settings.hcx_model != "HCX-DASH-002":
        raise SystemExit("P20은 GENERATOR_BACKEND=hcx 및 HCX-DASH-002에서만 실행합니다.")
    p19 = _p19_states(args.p19_preparation)
    questions = load_questions(args.questions)
    if set(p19) != {question.question_id for question in questions}:
        raise ValueError("P19 preparation and P20 question IDs must match exactly")

    agent = ConditionalRoutingShadowAgent(
        retriever=build_frozen_retriever(args.corpus, args.index),
        generator=build_answer_generator(settings),
    )
    started = time.perf_counter()
    rows = evaluate_agent(TestClient(create_app(agent)), questions)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)

    preparation_rows = []
    for row in rows:
        current = _p20_state(row)
        expected = p19[row["question_id"]]
        mismatch = [field for field in PARITY_FIELDS if current[field] != expected[field]]
        preparation_rows.append(
            {
                "question_id": row["question_id"],
                "p19": expected,
                "p20": current,
                "parity": not mismatch,
                "mismatch_fields": mismatch,
            }
        )
    parity_count = sum(row["parity"] for row in preparation_rows)
    payload = {
        "variant": "p20_conditional_shadow",
        "model": settings.hcx_model,
        "duration_ms": duration_ms,
        "p19_preparation_parity": f"{parity_count}/{len(preparation_rows)}",
        "summary": _operational_summary(rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.preparation_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.preparation_output.write_text(
        json.dumps({"parity": payload["p19_preparation_parity"], "rows": preparation_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"p19_preparation_parity": payload["p19_preparation_parity"], "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    if parity_count != len(preparation_rows):
        raise SystemExit("P20 preparation parity mismatch; HCX results were retained for diagnosis.")


if __name__ == "__main__":
    main()
