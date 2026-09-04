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
            "query_modality": "confirmation_uncertain",
            "claim_stance": {
                "stance": "contradict",
                "user_claim": "DB 적립금을 근로자가 운용한다",
                "supported_fact": "DB 적립금 운용 주체는 회사",
            },
            "selected_requirements": ["DB.operation_party"],
            "selected_evidence_chunk_ids": ["direct-db-evidence"],
            "cited_chunk_ids": ["direct-db-evidence"],
            "outcome": "supported_answer",
            "generation_model": "HCX-007",
            "generator_model": "HCX-007",
            "generator_prompt_version": "generator_prompt_final_v2_1",
            "generator_prompt_sha256": "05763afaa082af98832a04d29001a9d2ee1f353308cd4cc8e651e3b15b9c83a8",
        },
        request_id="request-1",
        endpoint="/answer",
        request_latency_ms=12.5,
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["question_sha256"]
    assert "question" not in record
    assert record["selected_requirements"] == ["DB.operation_party"]
    assert record["resolved_subject"] == "DB"
    assert record["query_modality"] == "confirmation_uncertain"
    assert record["claim_stance"] == "contradict"
    assert "DB 적립금을 근로자가 운용한다" not in path.read_text(encoding="utf-8")
    assert record["latency_ms"] == 12.5
    assert record["cited_chunk_ids"] == ["direct-db-evidence"]
    assert record["generator_model"] == "HCX-007"
    assert record["generator_prompt_version"] == "generator_prompt_final_v2_1"
    assert record["generator_prompt_sha256"] == "05763afaa082af98832a04d29001a9d2ee1f353308cd4cc8e651e3b15b9c83a8"


def test_jsonl_trace_can_include_question_when_explicitly_enabled(tmp_path):
    path = tmp_path / "answer_trace.log"
    writer = JsonlTraceWriter(JsonlTraceSettings(path=str(path), include_question=True))
    writer.record(question="DC 부담금?", think_trace={}, request_id=None, endpoint="/answer")
    assert json.loads(path.read_text(encoding="utf-8"))["question"] == "DC 부담금?"
