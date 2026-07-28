import json
from pathlib import Path

import pytest

from scripts.validate_retrieval_dataset import load_jsonl, validate


def test_retrieval_dataset_is_labeled_and_has_expected_splits():
    questions = load_jsonl(Path("evaluation/retrieval_questions.jsonl"))

    assert len(questions) == 40
    assert sum(question["split"] == "dev" for question in questions) == 30
    assert sum(question["split"] == "test" for question in questions) == 10
    assert all("pending_label" not in question["notes"] for question in questions)
    assert sum(question["answerable"] for question in questions) == 38


def test_retrieval_dataset_evidence_matches_local_corpus():
    corpus_path = Path("data/parsed/chunks.jsonl")
    if not corpus_path.exists():
        pytest.skip("재생성 가능한 Corpus가 현재 작업공간에 없습니다.")

    chunks = {chunk["chunk_id"]: chunk for chunk in load_jsonl(corpus_path)}
    errors = validate(load_jsonl(Path("evaluation/retrieval_questions.jsonl")), chunks)

    assert errors == []


def test_validator_rejects_wrong_source_locator():
    questions = [
        {
            "question_id": "R-test",
            "answerable": True,
            "notes": [],
            "evidence_requirement": "any",
            "relevant_chunks": [
                {"chunk_id": "chunk-1", "source_id": "wrong", "locator": {}, "relevance": 2}
            ],
            "relevant_source_ids": ["wrong"],
        }
    ]
    chunks = {"chunk-1": {"chunk_id": "chunk-1", "source_id": "source-1", "locator": {"page_start": 1}}}

    errors = validate(questions, chunks)

    assert any("source_id" in error for error in errors)
    assert any("locator" in error for error in errors)
