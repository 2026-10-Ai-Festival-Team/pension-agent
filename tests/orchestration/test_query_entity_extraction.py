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
    assert extracted.requested_fields == ["fee", "investment_target"]
