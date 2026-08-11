from src.experiments.query_understanding import RequirementBuilder, SupportClassifier
from src.orchestration.query_analyzer import QueryAnalyzer


def test_support_classifier_separates_personal_current_and_recommendation_requests():
    classifier = SupportClassifier()

    assert classifier.classify("제 IRP 계좌의 잔액을 알려주세요").category == "personal_account_lookup"
    assert classifier.classify("오늘 기준 최신 세액공제 한도는?").category == "unavailable_external_information"
    assert classifier.classify("가장 수익이 높은 상품을 골라 주세요").category == "unsupported_recommendation_or_prediction"
    assert classifier.classify("DC 부담금 기준은 무엇인가요?").supported


def test_support_classifier_does_not_treat_je_inside_a_korean_noun_as_possessive():
    classifier = SupportClassifier()

    decision = classifier.classify("DB제도와 DC제도의 적립금 운용 책임을 비교해 주세요.")

    assert decision.supported
    assert decision.category == "supported"


def test_support_classifier_keeps_korean_possessive_forms_as_personal_requests():
    classifier = SupportClassifier()

    assert classifier.classify("제가 다니는 회사의 적립금 운용수익률을 알려주세요.").category == "personal_account_lookup"


def test_support_classifier_detects_future_external_prediction_requests():
    classifier = SupportClassifier()

    assert classifier.classify("다음 달 퇴직연금 시장 전망을 알려주세요.").category == "unsupported_recommendation_or_prediction"


def test_requirement_builder_makes_cartesian_product_slots_for_multiple_codes():
    analysis = QueryAnalyzer().analyze("KR5113420013과 KR5113420015의 위험등급과 총보수를 비교해 주세요")

    plan = RequirementBuilder().build(analysis)

    assert plan.category == "product_fields"
    assert [slot.name for slot in plan.case.slots] == [
        "KR5113420013 risk_grade",
        "KR5113420013 fee",
        "KR5113420015 risk_grade",
        "KR5113420015 fee",
    ]


def test_requirement_builder_groups_shared_operation_comparison_as_one_requirement():
    analysis = QueryAnalyzer().analyze("DB와 DC형은 적립금을 누가 운용하나요?")

    plan = RequirementBuilder().build(analysis)

    assert plan.requirement_count == 1
    assert plan.category == "shared_operation_comparison"


def test_requirement_builder_recognizes_irp_annuity_age_and_duration_with_varied_surface_form():
    analysis = QueryAnalyzer().analyze("IRP 연금은 몇 살부터 받고, 지급은 최소 몇 년이어야 하나요?")

    plan = RequirementBuilder().build(analysis)

    assert plan.category == "annuity_age_and_duration"
    assert [slot.key for slot in plan.case.slots] == ["annuity_age", "annuity_duration"]
    assert all(slot.retrieval_query for slot in plan.case.slots)
