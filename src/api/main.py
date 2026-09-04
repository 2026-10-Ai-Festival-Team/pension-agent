import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from src.api.chat_page import CHAT_PAGE
from src.api.schemas import AnswerRequest, AnswerResponse, EvaluationAnswerResponse, Evidence
from src.generation.fake import FakeGenerator
from src.generation.factory import build_answer_generator
from src.config.generation import GenerationSettings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.agent import PensionAgent
from src.orchestration.retrieval_service import build_frozen_retriever
from src.observability.jsonl_trace import JsonlTraceWriter


def create_app(agent=None, shadow_observer=None, trace_writer=None) -> FastAPI:
    app = FastAPI(title="Pension Agent", version="0.1.0")
    app.state.agent = agent
    # P44 only: absent by default, never exposed through the response schema.
    app.state.shadow_observer = shadow_observer
    # NCP-1B: optional, read-only trace sink for CLA custom-log collection.
    # A trace write failure is never allowed to change a candidate answer.
    app.state.trace_writer = trace_writer

    def answer_with_optional_shadow(question: str, top_k: int, *, request_id=None, endpoint="/answer", question_id=None):
        request_started = time.perf_counter()
        result = app.state.agent.answer(question, top_k)
        # The browser must render exactly the contexts that were selected for
        # answer generation, never a second raw-BM25 candidate list.
        result["think_trace"]["displayed_evidence_chunk_ids"] = [
            item.chunk_id for item in result["retrieved_context"]
        ]
        observer = app.state.shadow_observer
        if observer is not None:
            try:
                observer.observe(question)
            except Exception:
                # Defensive boundary for third-party sinks/observers.  The
                # read-only observer itself contains normal runtime errors.
                pass
        writer = app.state.trace_writer
        if writer is not None:
            try:
                writer.record(
                    question=question,
                    think_trace=result["think_trace"],
                    request_id=request_id,
                    endpoint=endpoint,
                    question_id=question_id,
                    request_latency_ms=round((time.perf_counter() - request_started) * 1000, 3),
                )
            except Exception:
                # Observability is strictly read-only from the request's view.
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
        result = answer_with_optional_shadow(
            body.question,
            body.top_k,
            request_id=request.headers.get("X-Request-ID"),
        )
        evidence = [Evidence(chunk_id=item.chunk_id, source_id=item.source_id, source_path=item.source_path, locator=item.locator, element_ids=item.element_ids, score=item.score, text=item.text, source_type=item.source_type, authority_level=item.authority_level, as_of_date=item.as_of_date) for item in result["retrieved_context"]]
        return AnswerResponse(question=body.question, retrieved_context=evidence, think_trace=result["think_trace"], answer=result["answer"])

    @app.get("/answer", response_model=EvaluationAnswerResponse)
    def evaluation_answer(question_id: str, question: str, request: Request, top_k: int = 5):
        if request.app.state.agent is None:
            raise RuntimeError("Agent is not configured")
        result = answer_with_optional_shadow(
            question,
            top_k,
            request_id=request.headers.get("X-Request-ID"),
            question_id=question_id,
        )
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
    """Build the P49-R runtime from the frozen P42--P48 scoped path.

    There is deliberately no P27 fallback here.  A deployment that cannot
    satisfy the HCX-007 structured-selector contract must fail at startup
    rather than silently serving raw BM25 contexts.
    """
    settings = settings or GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007":
        raise RuntimeError("The browser runtime requires GENERATOR_BACKEND=hcx and HCX_MODEL=HCX-007.")
    limiter = GlobalMinIntervalLimiter(
        settings.hcx_min_interval_seconds,
        guard_seconds=settings.hcx_pacing_guard_seconds,
    )
    retriever = build_frozen_retriever(corpus_path, index_path)
    return create_app(
        DirectRequirementE2EAgent(
            scoped_selector=ResolverFirstScopedSelector(
                HCXDirectRequirementSelector(config=settings, rate_limiter=limiter),
            ),
            preparation=ScopedFrontendPreparationShadow(retriever),
            generator=build_answer_generator(settings, rate_limiter=limiter),
        ),
        trace_writer=JsonlTraceWriter.from_env(),
    )
