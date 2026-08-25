from src.generation.fake import FakeGenerator
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResponse, SearchResult
from src.orchestration.agent import PensionAgent
from src.orchestration.evidence_assessor import EvidenceAssessor
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.generation.errors import GenerationError


def result(*, source_type=SourceType.ORIGINAL, authority_level=AuthorityLevel.PRIMARY, as_of_date=None):
    return SearchResult(
        rank=1,
        chunk_id="original-1",
        source_id="source-1",
        source_path="guide.pdf",
        source_format="pdf",
        document_type="pension_guide",
        locator=ChunkLocator(page_start=2, page_end=2),
        element_ids=["element-1"],
        score=1.0,
        text="세액공제 관련 일반 안내입니다.",
        source_type=source_type,
        authority_level=authority_level,
        as_of_date=as_of_date,
    )


class Retriever:
    def __init__(self, item):
        self.item = item

    def search(self, query, top_k=5):
        return SearchResponse(query=query, tokenizer="simple", total_candidates=1, results=[self.item])


class CountingFakeGenerator(FakeGenerator):
    def __init__(self):
        self.call_count = 0

    def generate(self, **kwargs):
        self.call_count += 1
        return super().generate(**kwargs)


def test_tax_answer_has_evidence_and_contextual_notice():
    answer = PensionAgent(Retriever(result(as_of_date="2026-01-01")), FakeGenerator()).answer("IRP 세액공제는 어떻게 되나요?")["answer"]

    assert "[답변]" in answer
    assert "[근거]" in answer
    assert "[출처: guide.pdf, 2페이지, 기준일 2026-01-01, original-1]" in answer
    assert "[유의사항]" in answer
    assert "세무전문가" in answer


def test_augmented_evidence_alone_cannot_establish_financial_fact():
    assessment = EvidenceAssessor().assess(
        QueryAnalyzer().analyze("DB형 운용 주체는?"),
        [result(source_type=SourceType.AUGMENTED, authority_level=AuthorityLevel.SECONDARY)],
    )

    assert assessment.sufficient is False
    assert assessment.reason == "primary_original_evidence_missing"


def test_recommendation_without_conditions_is_a_clarification_not_a_recommendation():
    answer = PensionAgent(Retriever(result()), FakeGenerator()).answer("어떤 상품을 추천해 주세요")["answer"]

    assert "[확인 필요]" in answer
    assert "투자 기간" in answer
    assert "특정 상품을 추천" in answer


def test_future_market_prediction_is_blocked_as_out_of_scope():
    answer = PensionAgent(Retriever(result()), FakeGenerator()).answer("다음 달 퇴직연금 시장 전망을 알려주세요")["answer"]

    assert "제공 문서 범위를 벗어난" in answer


def test_best_product_wording_is_treated_as_a_recommendation_request():
    answer = PensionAgent(Retriever(result()), FakeGenerator()).answer("가장 좋은 펀드를 골라 주세요")["answer"]

    assert "[확인 필요]" in answer


def test_investment_profile_statement_is_not_allowed_to_turn_into_single_product_recommendation():
    generator = CountingFakeGenerator()
    result_data = PensionAgent(Retriever(result()), generator).answer(
        "투자 기간은 20년, 위험 성향은 안전, 운용 목적은 퇴직연금 노후준비"
    )

    assert generator.call_count == 0
    assert "특정 상품이 최고·무조건 안전하다고" in result_data["answer"]
    assert "위험등급·투자대상·총보수" in result_data["answer"]
    assert result_data["think_trace"]["financial_policy"]["recommendation_context"] is True


def test_period_and_aggressive_profile_is_limited_to_candidate_comparison():
    generator = CountingFakeGenerator()
    result_data = PensionAgent(Retriever(result()), generator).answer("10년 투자, 공격적 성향이야")

    assert generator.call_count == 0
    assert "후보 상품" in result_data["answer"]
    assert "[확인 필요]" in result_data["answer"]
    assert result_data["think_trace"]["financial_policy"]["profile_complete"] is True


def test_recommendation_without_all_three_conditions_is_clarified_before_generation():
    generator = CountingFakeGenerator()
    result_data = PensionAgent(Retriever(result()), generator).answer("원금 손실 절대 없는 상품 추천해줘")

    assert generator.call_count == 0
    assert "[확인 필요]" in result_data["answer"]
    assert "투자 기간" in result_data["answer"]
    assert "운용 목적" in result_data["answer"]


def test_product_risk_question_gets_a_contextual_risk_notice():
    item = result()
    item = item.model_copy(update={"product_codes": ["KR1234567890"], "text": "KR1234567890 투자위험등급 4등급"})
    answer = PensionAgent(Retriever(item), FakeGenerator()).answer("KR1234567890 상품은 안전하지?")["answer"]

    assert "[유의사항]" in answer
    assert "원금보장 여부" in answer


def test_unidentified_product_reference_is_not_answered_from_an_arbitrary_retrieved_product():
    generator = CountingFakeGenerator()
    response = PensionAgent(Retriever(result()), generator).answer("이 상품 안전해?")

    assert generator.call_count == 0
    assert "상품명 또는 상품코드" in response["answer"]
    assert response["think_trace"]["assessment_reason"] == "product_identification_required"


def test_general_system_question_does_not_get_a_product_or_legal_disclaimer():
    answer = PensionAgent(Retriever(result()), FakeGenerator()).answer("DB형 적립금은 누가 운용하나요?")["answer"]

    assert "원금보장 여부" not in answer
    assert "법률 해석" not in answer


def test_generation_validation_failure_is_not_presented_as_missing_evidence():
    class FailingGenerator:
        def generate(self, **_):
            raise GenerationError("invalid structured response")

    response = PensionAgent(Retriever(result()), FailingGenerator()).answer("DB형 적립금은 누가 운용하나요?")

    assert "관련 원본 근거는 찾았지만" in response["answer"]
    assert "충분한 근거를 확인하지 못했습니다" not in response["answer"]
    assert response["think_trace"]["generation_error"] == "GenerationError"


def test_withdrawal_document_question_keeps_source_bound_document_examples():
    item = result()
    item = item.model_copy(update={"text": (
        "DC 중도인출 신청 절차: 중도인출신청서와 증빙서류를 제출한다. "
        "무주택자 주택구입 사유의 구비서류는 주민등록등본, 건물등기사항증명서, "
        "지방세 세목별 과세증명서, 매매계약서 사본이다."
    )})
    analysis = QueryAnalyzer().analyze(
        "DC형 퇴직연금에서 퇴직하기 전에 적립금 일부를 꺼낼 때 어떤 증빙서류가 필요한가요?"
    )

    answer = FinancialAnswerPolicy().format_answer("법정사유별 증빙서류를 제출합니다.", analysis, [item])

    assert "주민등록등본" in answer
    assert "건물등기사항증명서" in answer
    assert "다른 법정사유" in answer


def test_recommendation_policy_uses_complete_profile_and_expanded_single_turn_conditions():
    policy = FinancialAnswerPolicy()

    incomplete = policy.recommendation_decision(
        QueryAnalyzer().analyze("연금저축으로 8년 투자할 생각인데 상품 하나 골라 주세요.")
    )
    complete = policy.recommendation_decision(
        QueryAnalyzer().analyze("IRP에서 노후자금으로 15년 이상 운용하고 가격 변동도 감수합니다. 한 상품을 찍기보다 비교해 주세요.")
    )

    assert incomplete.missing_conditions == ("위험 성향", "운용 목적")
    assert complete.profile_complete
    assert "투자 기간" not in complete.missing_conditions


def test_personal_tax_and_unsupported_blocks_are_specific_to_the_first_turn():
    policy = FinancialAnswerPolicy()
    tax = QueryAnalyzer().analyze("퇴직금을 연금으로 받을 때 세금을 가장 적게 내게 제게 맞는 방법을 정해 주세요.")

    assert policy.requires_personal_tax_clarification(tax)
    assert "개인 식별정보" in policy.format_unsupported_safety_block("personal_account_lookup")
    assert "미래 시장" in policy.format_unsupported_safety_block("unavailable_external_information")
    assert "내부 지시" in policy.format_unsupported_safety_block("prompt_injection")
