"""Typed access to the versioned retrieval evaluation dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    source_id: str
    relevance: int
    locator: dict[str, Any]


@dataclass(frozen=True)
class RetrievalQuestion:
    question_id: str
    split: str
    question: str
    category: str
    answerable: bool
    requires_ocr: bool
    product_codes: list[str]
    relevant_chunks: list[Evidence]
    relevant_source_ids: list[str]
    required_terms: list[str]
    evidence_requirement: str
    notes: list[str]

    @property
    def direct_evidence_ids(self) -> set[str]:
        return {item.chunk_id for item in self.relevant_chunks if item.relevance == 2}

    @property
    def all_relevant_ids(self) -> set[str]:
        return {item.chunk_id for item in self.relevant_chunks if item.relevance >= 1}


def load_questions(path: Path) -> list[RetrievalQuestion]:
    questions: list[RetrievalQuestion] = []
    question_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        try:
            evidence = [Evidence(**item) for item in data["relevant_chunks"]]
            loaded_question = RetrievalQuestion(
                question_id=data["question_id"],
                split=data["split"],
                question=data["question"],
                category=data["category"],
                answerable=data["answerable"],
                requires_ocr=data["requires_ocr"],
                product_codes=data["product_codes"],
                relevant_chunks=evidence,
                relevant_source_ids=data["relevant_source_ids"],
                required_terms=data["required_terms"],
                evidence_requirement=data["evidence_requirement"],
                notes=data["notes"],
            )
            if loaded_question.question_id in question_ids:
                raise ValueError(
                    f"{path}:{line_number}에 중복 question_id가 있습니다: {loaded_question.question_id}"
                )
            question_ids.add(loaded_question.question_id)
            questions.append(loaded_question)
        except KeyError as error:
            raise ValueError(f"{path}:{line_number}에 필수 필드가 없습니다: {error.args[0]}") from error
    return questions


def load_dataset_metadata(path: Path) -> dict[str, Any]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if not metadata.get("corpus_sha256"):
        raise ValueError(f"{path}에 corpus_sha256이 없습니다.")
    return metadata
