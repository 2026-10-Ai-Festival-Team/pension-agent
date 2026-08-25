from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.experiments.multi_evidence import EvidenceSelection, RequirementCase, RequirementSlot, SlotMatch
from src.experiments.p26_candidate_agent import P26CandidateAgent
from src.experiments.routing_gate import RouteDecision
from src.experiments.shadow_execution import ShadowExecutionPlan
from src.generation.bounded_evidence_prompt_builder import BoundedEvidencePromptBuilder
from src.generation.fake import FakeGenerator
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResult
from src.orchestration.evidence_assessor import EvidenceAssessment
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.query_analyzer import QueryAnalyzer


def _primary() -> SearchResult:
    return SearchResult(
        rank=1,
        chunk_id="dc-reason",
        score=1.0,
        text="DC형 퇴직연금은 법정 사유가 있을 때 중도인출할 수 있습니다.",
        source_id="source-dc",
        source_path="guide.pdf",
        source_format="pdf",
        document_type="guide",
        locator=ChunkLocator(page_start=3, page_end=3),
        source_type=SourceType.ORIGINAL,
        authority_level=AuthorityLevel.PRIMARY,
    )


def test_partial_requirement_evidence_calls_generator_with_bounded_outcome():
    evidence = _primary()
    supported = RequirementSlot("중도인출 가능 사유", ("법정 사유",))
    missing = RequirementSlot("사유별 증빙서류", ("증빙서류",))
    case = RequirementCase("test", "compound", (supported, missing), context_selection_required=True)
    selection = EvidenceSelection(
        case,
        (SlotMatch(supported, evidence, ("법정 사유",)), SlotMatch(missing, None, ())),
        (evidence,),
    )
    analysis = QueryAnalyzer().analyze("DC형 퇴직연금에서 중도인출 사유와 증빙서류를 알려주세요.")
    plan = ShadowExecutionPlan(
        analysis=analysis,
        route=RouteDecision("compound", [], case),
        requirement_case=case,
        base_results=(evidence,),
        candidate_results=(evidence,),
        selection=selection,
        contexts=(evidence,),
        assessment=EvidenceAssessment(
            False,
            "compound_requirements_incomplete",
            ["사유별 증빙서류"],
            ["dc-reason"],
            ["중도인출 가능 사유"],
            "partial",
        ),
    )
    agent = P26CandidateAgent(retriever=object(), generator=FakeGenerator())
    agent.prepare = lambda *_args, **_kwargs: plan

    response = agent.answer(analysis.question)

    assert response["think_trace"]["outcome"] == "bounded_answer"
    assert response["think_trace"]["evidence_status"] == "partial"
    assert response["think_trace"]["generator_called"] is True
    assert "사유별 증빙서류" in response["answer"]
    assert "확인된 근거 범위" in response["answer"]
    assert "dc-reason" in response["answer"]


def test_none_evidence_does_not_substitute_a_generic_fact():
    policy = FinancialAnswerPolicy()
    answer = policy.format_no_evidence_boundary(
        EvidenceAssessment(False, "no_retrieval_evidence", ["미래 위험등급"]),
        QueryAnalyzer().analyze("이 상품의 내년 위험등급은 몇 등급인가요?"),
    )

    assert "미래 위험등급" in answer
    assert "일반 안내문" in answer
    assert "현재는" not in answer


def test_bounded_prompt_keeps_supported_and_unsupported_fields_separate():
    prompt = BoundedEvidencePromptBuilder(
        supported_requirements=("현재 위험등급",),
        unsupported_requirements=("내년 위험등급",),
    ).build("상품의 내년 위험등급은?", [_primary()])

    assert "현재 위험등급" in prompt
    assert "내년 위험등급" in prompt
    assert "추측하거나" in prompt
