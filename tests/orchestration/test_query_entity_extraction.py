import pytest

from src.orchestration.query_analyzer import QueryAnalyzer


@pytest.mark.parametrize(
    ("question", "accounts", "comparison"),
    [
        ("DB와 DC의 차이", ["DB", "DC"], True),
        ("DB·DC 비교", ["DB", "DC"], True),
        ("DB형과 DC형", ["DB", "DC"], True),
        ("DB/DC 중 무엇", ["DB", "DC"], True),
        ("DB, DC 중", ["DB", "DC"], True),
        ("IRP에 납입", ["IRP"], False),
        ("IRP로 이전", ["IRP"], False),
        ("연금저축과 IRP를 비교", ["IRP", "연금저축"], True),
    ],
)
def test_extracts_accounts_with_korean_particles_and_symbols(question, accounts, comparison):
    extracted = QueryAnalyzer().extract_entities(question)

    assert extracted.accounts == accounts
    assert extracted.comparison is comparison


def test_extraction_is_case_insensitive_and_keeps_product_code():
    extracted = QueryAnalyzer().extract_entities("db형 KR510902511M의 세금")

    assert extracted.accounts == ["DB"]
    assert extracted.product_codes == ["KR510902511M"]
    assert extracted.tax_intent


def test_ascii_partial_words_do_not_match_account_abbreviations():
    extracted = QueryAnalyzer().extract_entities("DBMS와 DCON은 연금 계좌가 아닙니다")

    assert extracted.accounts == []


def test_extraction_identifies_multiple_product_information_fields():
    extracted = QueryAnalyzer().extract_entities("KR5110501016 상품의 총보수와 투자 대상을 확인하고 싶습니다")

    assert extracted.product_codes == ["KR5110501016"]
    assert extracted.requested_fields == ["total_fee", "investment_target"]


def test_extraction_keeps_product_fee_fields_semantically_distinct():
    extracted = QueryAnalyzer().extract_entities(
        "KR5110501016 상품의 총보수, 기타 비용, 1,000만원 투자 시 비용 예시를 구분해 주세요"
    )

    assert extracted.requested_fields == ["total_fee", "other_expenses", "example_cost"]


def test_extraction_identifies_investment_risk_without_misclassifying_it_as_risk_grade():
    extracted = QueryAnalyzer().extract_entities("KR5113420012 펀드의 주요 투자 위험은 무엇인가요?")

    assert extracted.requested_fields == ["investment_risk"]


def test_extraction_identifies_natural_language_investment_strategy_and_loss_exposure():
    extracted = QueryAnalyzer().extract_entities(
        "KR5111000001은 주식에 어느 정도 투자하는 전략이고 투자원금의 손실도 가능한가요?"
    )

    assert extracted.requested_fields == ["investment_strategy", "principal_loss_possible"]


def test_analysis_uses_korean_boundary_safe_extracted_accounts_for_legacy_entities():
    analysis = QueryAnalyzer().analyze("DB형과 DC형의 차이를 알려주세요")

    assert analysis.entities == ["DB", "DC"]


def test_resolves_verified_product_alias_to_code_and_canonical_name():
    extracted = QueryAnalyzer().extract_entities("미래에셋 장기성장포커스 1호의 위험등급은 몇 등급인가요?")

    assert extracted.product_codes == ["KR510902511M"]
    assert extracted.products == ["미래에셋장기성장포커스증권자투자신탁1호(주식)"]
    assert extracted.requested_fields == ["risk_grade"]


def test_named_objective_product_question_is_not_a_recommendation_request():
    analysis = QueryAnalyzer().analyze("미래에셋 장기성장포커스 1호는 어떤 상품이고 위험등급이 몇 등급인가요?")

    assert analysis.intent == "product_explanation"
    assert analysis.product_codes == ["KR510902511M"]


def test_objective_two_product_field_selection_is_not_a_recommendation_request():
    analysis = QueryAnalyzer().analyze(
        "KR5120420039와 KR5120420091 중 위험등급이 낮은 상품을 골라 주세요"
    )

    assert analysis.intent == "product_explanation"
    assert analysis.requires_user_conditions is False
