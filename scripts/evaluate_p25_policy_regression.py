"""P25-0: 기본 Agent의 provenance·금융 답변 정책을 HCX 없이 회귀 검증한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.policy_regression import (
    assess_policy_regression,
    provenance_migration_summary,
    summarize_policy_regression,
)
from src.evaluation.retrieval_dataset import load_questions
from src.orchestration.retrieval_service import build_frozen_retriever


def _load_p15(path: Path, labels_path: Path) -> list[tuple[str, str, bool]]:
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    labels = {
        item["question_id"]: item
        for item in json.loads(labels_path.read_text(encoding="utf-8"))["labels"]
    }
    return [
        (
            item["question_id"],
            item["question"],
            not labels[item["question_id"]]["evidence_sufficient_expected"],
        )
        for item in questions
    ]


def _markdown(payload: dict) -> str:
    full, p15, migration = payload["full_40"], payload["p15_mini_holdout"], payload["provenance_migration"]
    return "\n".join(
        [
            "# P25-0: Provenance·금융 답변 정책 회귀 검증",
            "",
            "HCX를 호출하지 않고 기본 `PensionAgent`의 기존 evidence gate와 provenance gate를 비교했다. 이 결과는 P24-B 실험 경로의 검색·matcher 성능을 측정하지 않는다.",
            "",
            "## 결과",
            "",
            "| 범위 | 문항 | provenance 신규 false rejection | augmented-only unsafe pass | 예상 차단 누락 |",
            "|---|---:|---:|---:|---:|",
            f"| Full-40 | {full['questions']} | {full['provenance_false_rejection']} | {full['augmented_only_unsafe_pass']} | {full['expected_rejection_missed']} |",
            f"| P15 mini-holdout | {p15['questions']} | {p15['provenance_false_rejection']} | {p15['augmented_only_unsafe_pass']} | {p15['expected_rejection_missed']} |",
            "",
            "## 답변 정책 확인",
            "",
            f"- 세제 유의사항 누락: {full['tax_notice_missing'] + p15['tax_notice_missing']}건",
            f"- 일반 제도 질문의 불필요한 유의사항: {full['general_notice_regression'] + p15['general_notice_regression']}건",
            f"- 추천 역질문 누락: {full['recommendation_clarification_missing'] + p15['recommendation_clarification_missing']}건",
            f"- 원본·1차 근거가 아닌 citation: {full['non_primary_citation'] + p15['non_primary_citation']}건",
            "",
            "## 기존 Corpus provenance migration",
            "",
            f"- 청크 수: {migration['chunk_count']}개",
            f"- `original + primary`: {migration['original_primary_count']}개",
            f"- `augmented`: {migration['augmented_count']}개",
            f"- 정책상 모순된 provenance 조합: {migration['invalid_provenance_combinations']}개",
            "",
            "## 해석",
            "",
            "`provenance 신규 false rejection`은 provenance 조건을 추가하기 전에는 통과했지만, 원본·1차 근거가 없어서 새로 차단된 경우만 뜻한다. 검색 recall이나 compound requirement completeness로 인한 기존 차단은 이 P25-0 지표에 포함하지 않는다.",
            "",
            "P25-0 통과 기준은 provenance 신규 false rejection 0, augmented-only unsafe pass 0, 예상 차단 누락 0이다.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/parsed/chunks.jsonl")
    parser.add_argument("--index", type=Path, default=ROOT / "data/indexes/bm25/simple")
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/retrieval_questions.jsonl")
    parser.add_argument("--p15-questions", type=Path, default=ROOT / "evaluation/p15_mini_holdout_questions.json")
    parser.add_argument("--p15-labels", type=Path, default=ROOT / "evaluation/p15_mini_holdout_labels.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p25_policy_regression.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/p25_policy_regression.md")
    args = parser.parse_args()

    retriever = build_frozen_retriever(args.corpus, args.index)
    full_rows = [
        assess_policy_regression(
            question_id=item.question_id,
            question=item.question,
            expected_rejection=not item.answerable,
            retriever=retriever,
        )
        for item in load_questions(args.questions)
    ]
    p15_rows = [
        assess_policy_regression(
            question_id=question_id,
            question=question,
            expected_rejection=expected_rejection,
            retriever=retriever,
        )
        for question_id, question, expected_rejection in _load_p15(args.p15_questions, args.p15_labels)
    ]
    payload = {
        "hcx_called": False,
        "full_40": summarize_policy_regression(full_rows),
        "p15_mini_holdout": summarize_policy_regression(p15_rows),
        "provenance_migration": provenance_migration_summary(retriever.retriever.index.chunks),
        "rows": {"full_40": full_rows, "p15_mini_holdout": p15_rows},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("full_40", "p15_mini_holdout", "provenance_migration")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
