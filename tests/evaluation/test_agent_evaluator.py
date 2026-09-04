from fastapi.testclient import TestClient
from src.api.main import create_app
from src.evaluation.agent_evaluator import evaluate_agent
from src.generation.fake import FakeGenerator
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult
from src.orchestration.agent import PensionAgent


class Retriever:
    def search(self, query, top_k=5):
        item=SearchResult(rank=1,chunk_id="gold",source_id="s",source_path="x.pdf",source_format="pdf",document_type="pension_guide",locator=ChunkLocator(page_start=1,page_end=1),element_ids=["e"],score=1,text="DB DC",metadata={"document_id":"DOC-TEST00000005"})
        return SearchResponse(query=query,tokenizer="simple",total_candidates=1,results=[item])


class Question:
    question_id="R-1"; question="DB와 DC 비교"; answerable=True; direct_evidence_ids={"gold"}


def test_evaluator_records_api_and_citation_success():
    rows=evaluate_agent(TestClient(create_app(PensionAgent(Retriever(),FakeGenerator()))),[Question()])
    assert rows[0]["failure_stage"] == "success"
    assert rows[0]["citation_valid"] is True
