from fastapi.testclient import TestClient
from src.api.main import create_app
from src.generation.fake import FakeGenerator
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


def test_answer_rejects_blank_question():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))
    assert client.post("/answer", json={"question": ""}).status_code == 422


def test_get_answer_uses_evaluation_contract():
    client = TestClient(create_app(PensionAgent(StubRetriever(), FakeGenerator())))
    response = client.get("/answer", params={"question_id": "Q-001", "question": "DB형 운용 주체는?"})
    assert response.status_code == 200
    body = response.json()
    assert body["question_id"] == "Q-001"
    assert "[c1] guide.pdf" in body["retrieved_context"]
    assert body["think_trace"]["evidence_sufficient"] is True
    assert "[출처: guide.pdf" in body["answer"]
