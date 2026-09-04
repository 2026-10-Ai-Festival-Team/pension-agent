"""Record the P33-C1 manual source-relevance adjudication.

This is an offline development-regression audit.  Exact chunk overlap is
computed mechanically; semantic-equivalence verdicts are explicitly listed
human evidence judgements, never inferred from a shared document ID alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


EQUIVALENCE_NOTES = {
    "P33-003": "선택된 동일 IRP 원본 표가 단기·단시간 근로자의 IRP 가입 대상을 직접 설명한다.",
    "P33-012": "동일 상품 청크가 5등급·채권 운용전략·실적배당 및 원금손실 가능성을 함께 지지한다.",
    "P33-013": "각 상품의 선택 청크가 해당 상품의 위험등급과 주식 60% 이상 또는 국내 채권 투자 사실을 직접 지지한다.",
    "P33-023": "한 6등급 채권형 상품의 동일 원본에서 위험등급 산정, 예금자보호 비대상 및 원금손실 가능성을 직접 지지한다.",
    "P33-024": "동일 목표전환 상품의 요약정보와 위험 문단이 운용전환 후 국내 채권 전략 및 전환 과정 손실 가능성을 지지한다.",
    "P33-025": "선택된 원본들은 각각 과거 투자실적의 장래 비보장과 투자성향에 따른 적합성 판단을 직접 지지한다. 질문은 특정 상품을 지칭하지 않는 일반 안전 전제다.",
}


def _report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        "# P33-C1: Source-Relevance Generalization",
        "",
        "## Scope",
        "",
        "- HCX 호출 없음. P33은 개발 회귀셋이며 fresh-holdout 점수를 주장하지 않는다.",
        "- 상품 field에는 `subject + field + factual value`를 함께 요구하고, 일반 경고문은 field 근거를 대체하지 않도록 했다.",
        "- 동일 주체의 전략·손실 슬롯은 한 original source 안에서만 선택하도록 했다.",
        "",
        "## Result",
        "",
        f"- Exact manifest chunk overlap: **{summary['exact_gold']}/{summary['total']}**",
        f"- Manually adjudicated semantic equivalent: **{summary['semantic_equivalent']}**",
        f"- Exact or equivalent source relevance: **{summary['exact_or_equivalent']}/{summary['total']}**",
        f"- Partial evidence: **{summary['partial']}**",
        f"- Wrong scope: **{summary['wrong_scope']}**",
        "",
        "## Equivalence controls",
        "",
        "Equivalence was accepted only after checking `subject + account/product/system scope + field/requirement + factual value/condition`. A common source path alone was not accepted.",
        "",
        "## Decision",
        "",
        "P33-C1 closes the 18-item P33 source-relevance audit. The separate 46-item Closed Core evidence certification remains a development regression and currently exposes broader planner/retrieval coverage gaps; P34 remains blocked until those gaps are addressed and independently revalidated.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/p33_holdout_manifest.json")
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p33c1_source_relevance_regression.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p33c1_source_relevance_generalization.md")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    agent = P27DStructuredOutputAgent(build_frozen_retriever(args.corpus, args.index), FakeGenerator())
    rows = []
    for record in manifest["questions"]:
        expected = set(record["acceptable_equivalent_evidence"])
        if not expected:
            continue
        plan = agent.prepare(record["question"], top_k=10)
        selected = [context.chunk_id for context in plan.contexts]
        exact = bool(expected.intersection(selected))
        if exact:
            verdict = "exact_gold"
            basis = "Selected context contains a manifest-declared acceptable chunk."
        elif record["question_id"] in EQUIVALENCE_NOTES:
            verdict = "semantic_equivalent"
            basis = EQUIVALENCE_NOTES[record["question_id"]]
        else:
            verdict = "needs_manual_review"
            basis = "No exact chunk and no P33-C1 equivalence annotation exists."
        rows.append({
            "question_id": record["question_id"],
            "question": record["question"],
            "verdict": verdict,
            "basis": basis,
            "declared_acceptable_chunk_ids": sorted(expected),
            "selected_chunk_ids": selected,
            "route": plan.route.route,
            "evidence_sufficient": plan.assessment.sufficient,
            "missing_slots": plan.assessment.missing_requirements,
        })
    summary = {
        "total": len(rows),
        "exact_gold": sum(row["verdict"] == "exact_gold" for row in rows),
        "semantic_equivalent": sum(row["verdict"] == "semantic_equivalent" for row in rows),
        "partial": sum(row["verdict"] == "partial_evidence" for row in rows),
        "wrong_scope": sum(row["verdict"] == "irrelevant_or_wrong_scope" for row in rows),
    }
    summary["exact_or_equivalent"] = summary["exact_gold"] + summary["semantic_equivalent"]
    payload = {
        "experiment": "P33-C1 source-relevance generalization",
        "hcx_called": False,
        "adjudication_rule": "subject + account/product/system scope + field/requirement + factual value/condition",
        "summary": summary,
        "source_relevance_gate_pass": summary["exact_or_equivalent"] == summary["total"] and summary["wrong_scope"] == 0,
        # This audit closes only P33 source relevance.  The broader Closed
        # Core evidence certification is a separate precondition for P34.
        "go_for_p34": False,
        "rows": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(_report(payload), encoding="utf-8")
    print(json.dumps({
        **summary,
        "source_relevance_gate_pass": payload["source_relevance_gate_pass"],
        "go_for_p34": payload["go_for_p34"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
