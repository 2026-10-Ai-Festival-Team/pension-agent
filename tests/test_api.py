from fastapi.testclient import TestClient

from src.agent.answer_generator import AnswerGenerator
from src.agent.question_analyzer import QuestionAnalyzer
from src.agent.service import PensionAgentService
from src.api.main import app
from src.retrieval.bm25_retriever import BM25Retriever


app.state.service = PensionAgentService(BM25Retriever([]), QuestionAnalyzer(None), AnswerGenerator(None))
client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_answer_without_index_abstains():
    response = client.get("/answer", params={"question_id": "Q1", "question": "문서에 없는 질문"})
    assert response.status_code == 200
    assert "충분한 근거" in response.json()["answer"]


def test_missing_and_blank_question():
    assert client.get("/answer", params={"question_id": "Q1"}).status_code == 422
    assert client.get("/answer", params={"question_id": "Q1", "question": " "}).status_code == 422
