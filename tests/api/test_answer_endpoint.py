from fastapi.testclient import TestClient
from src.api.main import create_app
from src.generation.fake import FakeGenerator
from src.generation.base import GenerationResult
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult
from src.orchestration.agent import PensionAgent


class StubRetriever:
    def search(self, query, top_k=5):
        result = SearchResult(rank=1, chunk_id="c1", source_id="s1", source_path="guide.pdf", source_format="pdf", document_type="pension_guide", locator=ChunkLocator(page_start=2, page_end=2), element_ids=["e1"], score=1.2, text="DB형은 회사가 운용합니다.")
        return SearchResponse(query=query, tokenizer="simple-ko-v1", total_candidates=1, results=[result])


def test_answer_keeps_structured_evidence():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))
    response = client.post("/answer", json={"question": "DB형 운용 주체는?"})
    assert response.status_code == 200
    body = response.json()
    assert body["retrieved_context"][0]["source_path"] == "guide.pdf"
    assert body["retrieved_context"][0]["locator"]["page_start"] == 2
    assert body["retrieved_context"][0]["element_ids"] == ["e1"]


def test_root_serves_a_browser_question_ui():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))

    response = client.get("/")

    assert response.status_code == 200
    assert "연금 Agent" in response.text
    assert "fetch('/answer'" in response.text


def test_answer_rejects_blank_question():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))
    assert client.post("/answer", json={"question": ""}).status_code == 422


def test_read_only_shadow_exception_does_not_change_candidate_response():
    class ExplodingShadow:
        def observe(self, _question):
            raise RuntimeError("shadow failure")

    response = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator()), ExplodingShadow())).post(
        "/answer", json={"question": "DB형 운용 주체는?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"]


def test_get_answer_uses_evaluation_contract():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))
    response = client.get("/answer", params={"question_id": "Q-001", "question": "DB형 운용 주체는?"})
    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == "Q-001"
    assert "[c1] guide.pdf" in body["retrieved_context"]
    assert body["think_trace"]["evidence_sufficient"] is True
    assert body["think_trace"]["cited_chunk_ids"] == ["c1"]
    assert body["think_trace"]["generator_attempted"] is True
    assert "[출처: guide.pdf" in body["answer"]


def test_unknown_citation_is_rejected_with_structured_reason():
    class UnknownCitationGenerator:
        def generate(self, **_):
            return GenerationResult("답변", ["unknown-chunk"], "test", 1.0)

    client = TestClient(create_app(PensionAgent(StubRetriever(), UnknownCitationGenerator())))
    response = client.get("/answer", params={"question_id": "Q-002", "question": "DB형 운용 주체는?"})

    body = response.json()
    assert body["think_trace"]["generator_called"] is False
    assert body["think_trace"]["generation_error"] == "CitationValidationError"
    assert body["think_trace"]["generation_diagnostic"]["citation_validation_reason"] == "unknown_chunk_id"
