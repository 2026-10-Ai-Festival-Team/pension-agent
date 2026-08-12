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

    assert plan.requirement_count == 2
    assert plan.category == "shared_operation_comparison"
    assert [slot.terms for slot in plan.case.slots] == [
        ("DB", "회사", "적립금 운용"),
        ("DC", "근로자", "적립금 운용"),
    ]


def test_requirement_builder_covers_db_dc_calculation_and_conversion_without_question_id_cases():
    builder = RequirementBuilder()

    calculation = builder.build(QueryAnalyzer().analyze("DB형과 DC형의 퇴직급여 산정 방식은 어떻게 다른가요?"))
    conversion = builder.build(QueryAnalyzer().analyze("DB 제도를 DC 제도로 바꿀 수 있는 조건은 무엇인가요?"))

    assert calculation.category == "db_dc_benefit_calculation"
    assert [slot.key for slot in calculation.case.slots] == ["db_benefit", "dc_benefit"]
    assert conversion.category == "db_dc_conversion"
    assert [slot.key for slot in conversion.case.slots] == ["conversion_eligibility", "conversion_conditions"]


def test_requirement_builder_covers_general_compound_comparison_and_tax_patterns():
    builder = RequirementBuilder()

    severance = builder.build(QueryAnalyzer().analyze("퇴직금 제도와 퇴직연금 제도는 어떤 차이가 있나요?"))
    classification = builder.build(QueryAnalyzer().analyze("원리금보장 운용방법과 채권형 펀드는 어떤 분류로 소개되나요?"))
    tax = builder.build(QueryAnalyzer().analyze("연금계좌를 해지할 때 세금상 불이익이 있나요?"))

    assert severance.category == "severance_and_pension_comparison"
    assert classification.category == "principal_and_bond_classification"
    assert tax.category == "account_cancellation_tax"


def test_requirement_builder_prioritizes_withdrawal_condition_and_procedure_over_single_condition():
    plan = RequirementBuilder().build(
        QueryAnalyzer().analyze("DC 가입자의 중도인출 가능 사유와 신청 서류를 같이 설명해 주세요.")
    )

    assert plan.category == "withdrawal_condition_and_procedure"
    assert [slot.key for slot in plan.case.slots] == ["dc_withdrawal_conditions", "withdrawal_procedure"]


def test_requirement_builder_recognizes_irp_annuity_age_and_duration_with_varied_surface_form():
    analysis = QueryAnalyzer().analyze("IRP 연금은 몇 살부터 받고, 지급은 최소 몇 년이어야 하나요?")

    plan = RequirementBuilder().build(analysis)

    assert plan.category == "annuity_age_and_duration"
    assert [slot.key for slot in plan.case.slots] == ["annuity_age", "annuity_duration"]
    assert all(slot.retrieval_query for slot in plan.case.slots)
