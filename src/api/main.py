from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request

load_dotenv()

from src.agent.answer_generator import AnswerGenerator
from src.agent.question_analyzer import QuestionAnalyzer
from src.agent.service import PensionAgentService
from src.config import get_settings
from src.llm.hyperclova import HyperClovaClient
from src.retrieval.bm25_retriever import BM25Retriever
from src.schemas.models import HealthResponse, PipelineResult

app = FastAPI(title="Pension AI Agent Baseline", version="0.1.0")


@lru_cache(maxsize=1)
def build_service() -> PensionAgentService:
    settings = get_settings()
    client = HyperClovaClient(settings.hcx_api_key, settings.hcx_request_id, settings.hcx_endpoint, settings.hcx_model, settings.hcx_timeout_seconds, settings.hcx_max_retries)
    return PensionAgentService(BM25Retriever.from_jsonl(settings.index_path), QuestionAnalyzer(client), AnswerGenerator(client), settings.retrieval_top_k)


def service_for(request: Request) -> PensionAgentService:
    return getattr(request.app.state, "service", None) or build_service()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.get("/answer", response_model=PipelineResult)
def answer(request: Request, question_id: str = Query(..., min_length=1, max_length=100), question: str = Query(..., min_length=1)) -> PipelineResult:
    settings = get_settings()
    if not question.strip():
        raise HTTPException(status_code=422, detail="question은 빈 문자열일 수 없습니다.")
    if len(question) > settings.max_question_length:
        raise HTTPException(status_code=413, detail=f"question은 {settings.max_question_length}자를 초과할 수 없습니다.")
    return service_for(request).answer(question_id.strip(), question.strip())
