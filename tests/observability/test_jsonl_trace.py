import json

from src.observability.jsonl_trace import JsonlTraceSettings, JsonlTraceWriter


def test_jsonl_trace_redacts_question_by_default(tmp_path):
    path = tmp_path / "answer_trace.log"
    writer = JsonlTraceWriter(JsonlTraceSettings(path=str(path)))

    writer.record(
        question="DB는 내가 직접 굴리는 거지?",
        think_trace={
            "route": "p45_single_subject_direct_requirement",
            "active_subject": "DB",
            "selected_requirements": ["DB.operation_party"],
            "selected_evidence_chunk_ids": ["direct-db-evidence"],
            "cited_chunk_ids": ["direct-db-evidence"],
            "outcome": "supported_answer",
            "generation_model": "HCX-007",
        },
        request_id="request-1",
        endpoint="/answer",
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["question_sha256"]
    assert "question" not in record
    assert record["selected_requirements"] == ["DB.operation_party"]
    assert record["cited_chunk_ids"] == ["direct-db-evidence"]


def test_jsonl_trace_can_include_question_when_explicitly_enabled(tmp_path):
    path = tmp_path / "answer_trace.log"
    writer = JsonlTraceWriter(JsonlTraceSettings(path=str(path), include_question=True))
    writer.record(question="DC 부담금?", think_trace={}, request_id=None, endpoint="/answer")
    assert json.loads(path.read_text(encoding="utf-8"))["question"] == "DC 부담금?"
