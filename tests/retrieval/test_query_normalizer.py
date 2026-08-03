from src.retrieval.query_normalizer import (
    PensionQueryNormalizer,
    build_default_pension_query_normalizer,
)
from src.retrieval.tokenizer import SimpleKoreanTokenizer


def test_normalizer_preserves_original_tokens():
    tokenizer = SimpleKoreanTokenizer()
    query = "퇴직연금 계좌를 다른 금융회사로 이전할 수 있나요?"

    tokens = build_default_pension_query_normalizer().expand(query, tokenizer)

    assert set(tokenizer.tokenize(query)).issubset(tokens)


def test_normalizer_adds_document_term():
    tokens = build_default_pension_query_normalizer().expand(
        "퇴직연금 계좌를 다른 금융회사로 이전할 수 있나요?", SimpleKoreanTokenizer()
    )

    assert "사업자이전" in tokens
    assert "계약이전" in tokens


def test_normalizer_is_deterministic():
    normalizer = build_default_pension_query_normalizer()
    tokenizer = SimpleKoreanTokenizer()

    assert normalizer.expand("세금상 불이익이 있나요?", tokenizer) == normalizer.expand("세금상 불이익이 있나요?", tokenizer)


def test_normalizer_does_not_modify_product_code():
    tokenizer = SimpleKoreanTokenizer()
    query = "KR510902511M 상품의 투자대상은 무엇인가요?"

    assert build_default_pension_query_normalizer().expand(query, tokenizer) == tokenizer.tokenize(query)


def test_normalizer_preserves_protected_abbreviations_and_values():
    tokenizer = SimpleKoreanTokenizer()
    query = "DB DC IRP 900만원 16.5% 55세 2026년 2026-01-01 1등급 5등급"

    assert build_default_pension_query_normalizer().expand(query, tokenizer) == tokenizer.tokenize(query)


def test_normalizer_does_not_merge_distinct_tax_terms():
    tokens = build_default_pension_query_normalizer().expand("세액공제 대상은 무엇인가요?", SimpleKoreanTokenizer())

    assert "소득공제" not in tokens
    assert "연금소득세" not in tokens


def test_company_operation_expansion_preserves_original_terms():
    normalizer = PensionQueryNormalizer({"회사가 운용": ["사용자 운용"]}, {})
    tokens = normalizer.expand("DB는 회사가 운용하나요?", SimpleKoreanTokenizer())

    assert "회사" in tokens
    assert "사용자" in tokens
    assert "운용" in tokens
