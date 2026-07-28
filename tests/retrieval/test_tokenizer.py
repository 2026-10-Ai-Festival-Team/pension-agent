from src.retrieval.tokenizer import SimpleKoreanTokenizer
def test_simple_tokenizer_preserves_codes_and_numbers():
    tokens=SimpleKoreanTokenizer().tokenize("KR1234567890 IRP DB DC 16.5% 900만원 2026년 퇴직연금 세액공제")
    assert {"kr1234567890","irp","db","dc","16.5%","900만원","2026년","퇴직연금","세액공제"}.issubset(tokens)
