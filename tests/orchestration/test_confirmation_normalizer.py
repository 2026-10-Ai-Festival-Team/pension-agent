import pytest

from src.orchestration.confirmation_normalizer import normalize_confirmation_query


@pytest.mark.parametrize(
    ("question", "modality"),
    (
        ("DB는 내가 직접 굴리는 거 맞지? 아닌가?", "confirmation_uncertain"),
        ("DB는 내가 직접 굴리는 거 맞나?", "confirmation"),
        ("제 기억엔 DB는 회사가 굴리는 건데 맞나요?", "confirmation"),
        ("DB는 내가 직접 굴리는 줄 알았는데 아닌가?", "confirmation_uncertain"),
        ("DB는 내가 직접 굴리는 거 아니야?", "confirmation"),
    ),
)
def test_confirmation_normalizer_preserves_the_operation_proposition(question, modality):
    result = normalize_confirmation_query(question)

    assert "DB" in result.proposition_core
    assert "굴리" in result.proposition_core
    assert result.query_modality == modality


def test_scope_exclusion_is_not_normalized_as_confirmation_modality():
    result = normalize_confirmation_query("IRP 말고 연금저축만 납입하면 한도는 얼마인가요?")

    assert result.proposition_core == "IRP 말고 연금저축만 납입하면 한도는 얼마인가요?"
    assert result.query_modality == "neutral"


@pytest.mark.parametrize(
    ("question", "required_marker"),
    (
        ("IRP로 옮기면 운용 중에는 세금 안 내는 거 맞지?", "세금 안 내는"),
        ("KR5111420047 상품이 지금 5등급인 거 맞나?", "5등급"),
        ("KR5111420047 총보수랑 기간별 비용이 같은 거 아니야?", "기간별 비용"),
    ),
)
def test_confirmation_normalizer_keeps_non_operation_factual_dimensions(question, required_marker):
    result = normalize_confirmation_query(question)

    assert required_marker in result.proposition_core
    assert result.query_modality != "neutral"
