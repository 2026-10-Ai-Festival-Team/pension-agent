import json
from pathlib import Path

from scripts.collect_retrieval_candidates import collect_candidates, load_questions
from src.models.chunk import ChunkLocator, ChunkType, SearchChunk


def make_chunk(chunk_id: str, text: str) -> SearchChunk:
    return SearchChunk(
        chunk_id=chunk_id,
        source_id="source-1",
        source_path="docs_renamed/doc1.pdf",
        source_format="pdf",
        document_type="pension_guide",
        chunk_type=ChunkType.PARAGRAPH_GROUP,
        text=text,
        locator=ChunkLocator(page_start=1, page_end=1),
        element_ids=[f"{chunk_id}-element"],
    )


def test_questions_have_expected_split_and_labeled_state():
    questions = load_questions(Path("evaluation/retrieval_questions.jsonl"))

    assert len(questions) == 40
    assert sum(question["split"] == "dev" for question in questions) == 30
    assert sum(question["split"] == "test" for question in questions) == 10
    assert all("pending_label" not in question["notes"] for question in questions)
    assert all(question["relevant_chunks"] for question in questions if question["answerable"])
    assert all(not question["relevant_chunks"] for question in questions if not question["answerable"])


def test_collection_keeps_union_scores_and_source_location():
    question = {
        "question_id": "R-test",
        "question": "DB형은 누가 운용하나요?",
        "answerable": True,
    }
    rows = collect_candidates(
        [
            make_chunk("db", "DB형 적립금은 회사가 운용합니다."),
            make_chunk("dc", "DC형은 근로자가 운용합니다."),
            make_chunk("irp", "IRP는 개인형 퇴직연금입니다."),
        ],
        [question],
        top_k=2,
    )

    assert rows[0]["simple"]["tokenizer"] == "simple-ko-v1"
    assert rows[0]["kiwi"]["tokenizer"] == "kiwi-ko-v1"
    assert rows[0]["candidates"]
    candidate = rows[0]["candidates"][0]
    assert candidate["source_path"] == "docs_renamed/doc1.pdf"
    assert candidate["locator"] == {"page_start": 1, "page_end": 1, "slide_start": None, "slide_end": None, "sheet": None, "cell_range": None}
    assert candidate["simple_rank"] is not None or candidate["kiwi_rank"] is not None


def test_candidate_output_is_json_serializable():
    rows = collect_candidates([make_chunk("db", "DB형 회사 운용")], [{"question_id": "R-test", "question": "DB 운용"}], top_k=1)
    assert json.loads(json.dumps(rows, ensure_ascii=False))[0]["question_id"] == "R-test"
