from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from src.api.chat_page import CHAT_PAGE
from src.api.schemas import AnswerRequest, AnswerResponse, EvaluationAnswerResponse, Evidence
from src.generation.fake import FakeGenerator
from src.generation.factory import build_answer_generator
from src.config.generation import GenerationSettings
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.orchestration.agent import PensionAgent
from src.orchestration.retrieval_service import build_frozen_retriever


def create_app(agent=None, shadow_observer=None) -> FastAPI:
    app = FastAPI(title="Pension Agent", version="0.1.0")
    app.state.agent = agent
    # P44 only: absent by default, never exposed through the response schema.
    app.state.shadow_observer = shadow_observer

    def answer_with_optional_shadow(question: str, top_k: int):
        result = app.state.agent.answer(question, top_k)
        observer = app.state.shadow_observer
        if observer is not None:
            try:
                observer.observe(question)
            except Exception:
                # Defensive boundary for third-party sinks/observers.  The
                # read-only observer itself contains normal runtime errors.
                pass
        return result

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def chat_page():
        return HTMLResponse(CHAT_PAGE)

    @app.get("/health")
    def health(): return {"status": "ok"}

    @app.post("/answer", response_model=AnswerResponse)
    def answer(body: AnswerRequest, request: Request):
        if request.app.state.agent is None:
            raise RuntimeError("Agent is not configured")
        result = answer_with_optional_shadow(body.question, body.top_k)
        evidence = [Evidence(chunk_id=item.chunk_id, source_id=item.source_id, source_path=item.source_path, locator=item.locator, element_ids=item.element_ids, score=item.score, text=item.text, source_type=item.source_type, authority_level=item.authority_level, as_of_date=item.as_of_date) for item in result["retrieved_context"]]
        return AnswerResponse(question=body.question, retrieved_context=evidence, think_trace=result["think_trace"], answer=result["answer"])

    @app.get("/answer", response_model=EvaluationAnswerResponse)
    def evaluation_answer(question_id: str, question: str, request: Request, top_k: int = 5):
        if request.app.state.agent is None:
            raise RuntimeError("Agent is not configured")
        result = answer_with_optional_shadow(question, top_k)
        context_text = "\n\n".join(f"[{item.chunk_id}] {item.source_path}\n{item.text}" for item in result["retrieved_context"])
        return EvaluationAnswerResponse(question_id=question_id, question=result["question"], retrieved_context=context_text, think_trace=result["think_trace"], answer=result["answer"])
    return app


app = create_app()


def create_local_app(corpus_path, index_path) -> FastAPI:
    """Development composition root for the frozen retrieval baseline."""
    return create_app(PensionAgent(build_frozen_retriever(corpus_path, index_path), FakeGenerator()))


def create_configured_app(corpus_path, index_path, settings=None) -> FastAPI:
    settings = settings or GenerationSettings.from_env()
    return create_app(PensionAgent(build_frozen_retriever(corpus_path, index_path), build_answer_generator(settings)))


def create_browser_configured_app(corpus_path, index_path, settings=None) -> FastAPI:
    """Browser/API composition with the validated requirement and native-SO path.

    ``PensionAgent`` remains available as the minimal baseline for tests and
    experiments.  The user-facing endpoint needs the same requirement-bound
    evidence selection and HCX-007 structured-output contract that protect the
    evaluated candidate path.
    """
    settings = settings or GenerationSettings.from_env()
    return create_app(
        P27DStructuredOutputAgent(
            build_frozen_retriever(corpus_path, index_path),
            build_answer_generator(settings),
        )
    )
