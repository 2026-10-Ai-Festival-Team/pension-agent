from fastapi import FastAPI, Request
from src.api.schemas import AnswerRequest, AnswerResponse, EvaluationAnswerResponse, Evidence
from src.generation.fake import FakeGenerator
from src.orchestration.agent import PensionAgent
from src.orchestration.retrieval_service import build_frozen_retriever


def create_app(agent=None) -> FastAPI:
    app = FastAPI(title="Pension Agent", version="0.1.0")
    app.state.agent = agent

    @app.get("/health")
    def health(): return {"status": "ok"}

    @app.post("/answer", response_model=AnswerResponse)
    def answer(body: AnswerRequest, request: Request):
        if request.app.state.agent is None:
            raise RuntimeError("Agent is not configured")
        result = request.app.state.agent.answer(body.question, body.top_k)
        evidence = [Evidence(chunk_id=item.chunk_id, source_id=item.source_id, source_path=item.source_path, locator=item.locator, element_ids=item.element_ids, score=item.score, text=item.text) for item in result["retrieved_context"]]
        return AnswerResponse(question=body.question, retrieved_context=evidence, think_trace=result["think_trace"], answer=result["answer"])

    @app.get("/answer", response_model=EvaluationAnswerResponse)
    def evaluation_answer(question_id: str, question: str, request: Request, top_k: int = 5):
        if request.app.state.agent is None:
            raise RuntimeError("Agent is not configured")
        result = request.app.state.agent.answer(question, top_k)
        context_text = "\n\n".join(f"[{item.chunk_id}] {item.source_path}\n{item.text}" for item in result["retrieved_context"])
        return EvaluationAnswerResponse(question_id=question_id, question=result["question"], retrieved_context=context_text, think_trace=result["think_trace"], answer=result["answer"])
    return app


app = create_app()


def create_local_app(corpus_path, index_path) -> FastAPI:
    """Development composition root for the frozen retrieval baseline."""
    return create_app(PensionAgent(build_frozen_retriever(corpus_path, index_path), FakeGenerator()))
