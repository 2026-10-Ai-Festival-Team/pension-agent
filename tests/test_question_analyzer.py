from src.agent.question_analyzer import QuestionAnalyzer


def test_factual_question_does_not_clarify():
    result = QuestionAnalyzer(None).analyze("IRP와 연금저축의 중도인출 사유가 같은가요?")
    assert result.needs_clarification is False


def test_vague_recommendation_clarifies():
    result = QuestionAnalyzer(None).analyze("좋은 연금 상품 하나만 추천해 주세요.")
    assert result.needs_clarification is True
    assert "위험 감내 수준" in result.missing_information


def test_named_comparison_does_not_clarify():
    result = QuestionAnalyzer(None).analyze("A펀드와 B펀드를 위험등급 중심으로 비교해 주세요.")
    assert result.needs_clarification is False
