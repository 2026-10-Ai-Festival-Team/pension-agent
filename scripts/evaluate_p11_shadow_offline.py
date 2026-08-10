"""P11: 전체 40문항 Shadow Router/Gate의 offline 일반화 검사.

HCX를 호출하지 않는다. 이 결과는 P10 실험을 production에 통합해도 되는지
판정하기 위한 사전 안전 점검이며, direct gold hit과 semantic sufficiency를
의도적으로 구분해 기록한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.retrieval_dataset import load_questions
from src.experiments.multi_evidence import load_requirement_cases
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.retrieval_service import build_frozen_retriever

P9_DEV_IDS = {
    f"R-{number:03d}"
    for number in (1, 2, 3, 4, 7, 9, 10, 11, 13, 24, 27, 28, 37, 39, 40)
}


def metrics(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row["gold_route"] != "unsupported"]
    known_sufficiency = [
        row for row in answerable
        if row["semantic_retrieval_sufficiency"] in {"full", "partial", "none"}
    ]
    return {
        "cases": len(rows),
        "routing_accuracy": round(
            sum(row["route_correct"] for row in rows) / len(rows), 3
        ),
        "misrouted": sum(not row["route_correct"] for row in rows),
        "false_rejection_known": sum(
            row["semantic_retrieval_sufficiency"] == "full"
            and not row["expected_hcx_call"]
            for row in known_sufficiency
        ),
        "unsafe_pass_known": sum(
            row["semantic_retrieval_sufficiency"] in {"partial", "none"}
            and row["expected_hcx_call"]
            for row in known_sufficiency
        ),
        "unknown_sufficiency": sum(
            row["semantic_retrieval_sufficiency"] == "unknown"
            for row in answerable
        ),
        "exact_direct_gold_miss_and_pass": sum(
            not row["direct_gold_hit"] and row["expected_hcx_call"]
            for row in answerable
        ),
        "expected_hcx_calls": sum(row["expected_hcx_call"] for row in answerable),
    }


def failure_owner(row: dict) -> str:
    if not row["route_correct"]:
        return "router"
    if row["semantic_retrieval_sufficiency"] == "full" and not row["expected_hcx_call"]:
        return "requirement_template_or_gate"
    if (
        row["semantic_retrieval_sufficiency"] in {"partial", "none"}
        and row["expected_hcx_call"]
    ):
        return "gate"
    if row["semantic_retrieval_sufficiency"] == "unknown":
        return "not_evaluable"
    return "none"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument(
        "--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl"
    )
    parser.add_argument(
        "--labels", type=Path, default=ROOT / "evaluation/p11_full40_routing_labels.json"
    )
    parser.add_argument(
        "--requirements", type=Path, default=ROOT / "evaluation/p5_multi_evidence_cases.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/diagnostics/p11_shadow_offline.json"
    )
    args = parser.parse_args()

    questions = {item.question_id: item for item in load_questions(args.questions)}
    labels = json.loads(args.labels.read_text(encoding="utf-8"))["labels"]
    requirement_cases = {
        item.question_id: item for item in load_requirement_cases(args.requirements)
    }
    retriever = build_frozen_retriever(args.corpus, args.index)
    analyzer = QueryAnalyzer()
    router = ExperimentalRouter()
    gate = ExperimentalRouteGate()
    rows = []

    for label in labels:
        question = questions[label["question_id"]]
        analysis = analyzer.analyze(question.question)
        route = router.classify(analysis)
        results = retriever.search(question.question, top_k=10).results
        requirement_case = requirement_cases.get(question.question_id)
        decision = gate.assess(route.route, analysis, results, requirement_case)
        retrieved_ids = {item.chunk_id for item in results}
        direct_gold_hit = bool(question.direct_evidence_ids & retrieved_ids)
        expected_hcx_call = decision.sufficient
        row = {
            "question_id": question.question_id,
            "p9_dev": question.question_id in P9_DEV_IDS,
            "gold_route": label["gold_route"],
            "predicted_route": route.route,
            "route_reasons": route.reasons,
            "route_correct": route.route == label["gold_route"],
            "extracted_entities": {
                "accounts": list(analysis.extracted_entities.accounts),
                "product_codes": list(analysis.extracted_entities.product_codes),
                "comparison": analysis.extracted_entities.comparison,
                "tax_intent": analysis.extracted_entities.tax_intent,
            },
            "required_slots": (
                [slot.name for slot in requirement_case.slots]
                if requirement_case is not None else []
            ),
            "direct_gold_hit": direct_gold_hit,
            "semantic_retrieval_sufficiency": label["evidence_sufficiency"],
            "gate_decision": decision.reason,
            "evidence_sufficient": decision.sufficient,
            "missing_slots": decision.missing_slots,
            "expected_hcx_call": expected_hcx_call,
            "baseline_outcome": "not_run_in_p11_offline",
            "shadow_outcome": "would_call_hcx" if expected_hcx_call else "pre_generation_rejection",
            "citation_result": "not_run_in_p11_offline",
            "semantic_labels": "not_run_in_p11_offline",
            "latency_ms": None,
        }
        row["failure_owner"] = failure_owner(row)
        rows.append(row)

    p9_dev = [row for row in rows if row["p9_dev"]]
    non_p9 = [row for row in rows if not row["p9_dev"]]
    payload = {
        "experiment": "P11 shadow offline routing/gate",
        "hcx_called": False,
        "summary": {
            "p9_dev": metrics(p9_dev),
            "non_p9": metrics(non_p9),
            "full40": metrics(rows),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
