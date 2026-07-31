import json
from pathlib import Path

import pytest

from scripts.validate_retrieval_dataset import load_jsonl, validate
from src.evaluation.retrieval_dataset import load_questions
from src.evaluation.retrieval_evaluator import sha256_file


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


def test_loader_rejects_duplicate_question_ids(tmp_path):
    question = {
        "question_id": "R-duplicate",
        "split": "dev",
        "question": "질문",
        "category": "test",
        "answerable": False,
        "requires_ocr": False,
        "product_codes": [],
        "relevant_chunks": [],
        "relevant_source_ids": [],
        "required_terms": [],
        "evidence_requirement": "any",
        "notes": [],
    }
    path = tmp_path / "questions.jsonl"
    path.write_text("\n".join([json.dumps(question), json.dumps(question)]), encoding="utf-8")

    with pytest.raises(ValueError, match="중복 question_id"):
        load_questions(path)


def test_dataset_metadata_matches_local_corpus():
    corpus_path = Path("data/parsed/chunks.jsonl")
    if not corpus_path.exists():
        pytest.skip("재생성 가능한 Corpus가 현재 작업공간에 없습니다.")

    metadata = json.loads(Path("evaluation/retrieval_dataset_meta.json").read_text(encoding="utf-8"))
    assert metadata["corpus_sha256"] == sha256_file(corpus_path)
