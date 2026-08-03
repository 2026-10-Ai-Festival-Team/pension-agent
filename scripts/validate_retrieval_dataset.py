"""Validate retrieval-evaluation evidence against the current search corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VALID_EVIDENCE_REQUIREMENTS = {"any", "all", "at_least_n"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate(questions: list[dict[str, Any]], chunks: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    question_ids = [question.get("question_id") for question in questions]
    if len(question_ids) != len(set(question_ids)):
        errors.append("question_id가 중복됩니다.")

    for question in questions:
        question_id = question.get("question_id", "<unknown>")
        evidence = question.get("relevant_chunks", [])
        if "pending_label" in question.get("notes", []):
            errors.append(f"{question_id}: pending_label이 남아 있습니다.")
        if question.get("evidence_requirement") not in VALID_EVIDENCE_REQUIREMENTS:
            errors.append(f"{question_id}: evidence_requirement 값이 올바르지 않습니다.")
        if question.get("answerable") and not evidence:
            errors.append(f"{question_id}: 답변 가능한 질문에 정답 근거가 없습니다.")
        if not question.get("answerable"):
            if evidence or question.get("relevant_source_ids"):
                errors.append(f"{question_id}: 답변 불가능 질문에는 정답 근거가 없어야 합니다.")
            if "unsupported_question" not in question.get("notes", []):
                errors.append(f"{question_id}: 답변 불가능 사유가 기록되지 않았습니다.")

        source_ids: set[str] = set()
        seen_chunk_ids: set[str] = set()
        for item in evidence:
            chunk_id = item.get("chunk_id")
            if chunk_id in seen_chunk_ids:
                errors.append(f"{question_id}: 정답 chunk_id가 중복됩니다: {chunk_id}")
                continue
            seen_chunk_ids.add(chunk_id)
            chunk = chunks.get(chunk_id)
            if chunk is None:
                errors.append(f"{question_id}: Corpus에 없는 chunk_id입니다: {chunk_id}")
                continue
            source_ids.add(item.get("source_id", ""))
            if item.get("source_id") != chunk["source_id"]:
                errors.append(f"{question_id}: source_id가 Corpus와 다릅니다: {chunk_id}")
            if item.get("locator") != chunk["locator"]:
                errors.append(f"{question_id}: locator가 Corpus와 다릅니다: {chunk_id}")
            if item.get("relevance") not in {1, 2}:
                errors.append(f"{question_id}: relevance는 1 또는 2여야 합니다: {chunk_id}")
        if set(question.get("relevant_source_ids", [])) != source_ids:
            errors.append(f"{question_id}: relevant_source_ids가 정답 근거와 다릅니다.")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    args = parser.parse_args()

    chunks = {chunk["chunk_id"]: chunk for chunk in load_jsonl(args.corpus)}
    errors = validate(load_jsonl(args.questions), chunks)
    if errors:
        raise SystemExit("\n".join(errors))
    print("검색 평가셋 검증 완료")


if __name__ == "__main__":
    main()
