from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.fake import FakeGenerator
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult


def _result(chunk_id: str, text: str) -> SearchResult:
    return SearchResult(
        rank=1,
        chunk_id=chunk_id,
        score=1.0,
        text=text,
        source_id="source",
        source_path="guide.pdf",
        source_format="pdf",
        document_type="guide",
        locator=ChunkLocator(page_start=1, page_end=1),
    )


class _Retriever:
    def search(self, question: str, top_k: int):
        if "개인형퇴직연금" in question:
            return SearchResponse(
                query=question,
                tokenizer="simple",
                total_candidates=1,
                results=[_result("irp-law", "개인형퇴직연금제도(IRP)는 55 세 이상, 연금 지급기간 5 년 이상입니다.")],
            )
        return SearchResponse(
            query=question,
            tokenizer="simple",
            total_candidates=1,
            results=[_result("base", "IRP 관련 근거입니다.")],
        )


def test_shadow_agent_blocks_unsupported_without_generator_call():
    agent = ConditionalRoutingShadowAgent(_Retriever(), FakeGenerator())

    answer = agent.answer("제 IRP 계좌의 잔액을 알려주세요.", top_k=10)

    assert not answer["think_trace"]["generator_attempted"]
    assert answer["think_trace"]["route"] == "unsupported"


def test_shadow_agent_uses_minimal_compound_context_after_requirement_gate():
    agent = ConditionalRoutingShadowAgent(_Retriever(), FakeGenerator())

    answer = agent.answer("IRP 연금은 몇 살부터 받고, 지급은 최소 몇 년이어야 하나요?", top_k=10)

    assert answer["think_trace"]["route"] == "compound"
    assert answer["think_trace"]["evidence_sufficient"]
    assert answer["think_trace"]["generator_called"]
    assert answer["think_trace"]["retrieved_chunk_ids"] == ["irp-law"]


def test_shadow_prepare_and_answer_share_same_compound_context():
    agent = ConditionalRoutingShadowAgent(_Retriever(), FakeGenerator())
    question = "IRP 연금은 몇 살부터 받고, 지급은 최소 몇 년이어야 하나요?"

    plan = agent.prepare(question, top_k=10)
    answer = agent.answer(question, top_k=10)

    assert plan.assessment.sufficient
    assert [item.chunk_id for item in plan.contexts] == answer["think_trace"]["retrieved_chunk_ids"]
    assert [item.chunk_id for item in plan.candidate_results] == answer["think_trace"]["candidate_chunk_ids"]


def test_shadow_trace_records_complete_pre_generation_state():
    agent = ConditionalRoutingShadowAgent(_Retriever(), FakeGenerator())

    answer = agent.answer("IRP 연금은 몇 살부터 받고, 지급은 최소 몇 년이어야 하나요?", top_k=10)
    trace = answer["think_trace"]

    assert trace["extracted_entities"]["accounts"] == ["IRP"]
    assert trace["requirement_plan"]["category"] == "annuity_age_and_duration"
    assert trace["base_retrieved_chunk_ids"] == ["base"]
    assert trace["candidate_chunk_ids"] == ["base", "irp-law"]
    assert trace["selected_merged_evidence_ids"] == ["irp-law"]
