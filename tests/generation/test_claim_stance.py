from src.generation.claim_stance import resolve_claim_stance
import pytest


def test_db_worker_confirmation_is_contradicted_by_db_operation_party_requirement():
    stance = resolve_claim_stance("DB는 내가 직접 굴리는 거 맞지? 아닌가?", ("DB.operation_party",))

    assert stance.stance == "contradict"
    assert stance.answer_prefix == "아니요."
    assert stance.apply_answer_prefix("네, 맞습니다. DB형 적립금의 운용 주체는 회사입니다.") == (
        "아니요. DB형 적립금의 운용 주체는 회사입니다."
    )
    assert stance.query_modality == "confirmation_uncertain"
    assert stance.claim_polarity == "positive"


def test_dc_company_confirmation_is_contradicted_by_dc_operation_party_requirement():
    stance = resolve_claim_stance("DC는 회사가 직접 굴리는 거죠?", ("DC.operation_party",))

    assert stance.stance == "contradict"
    assert stance.supported_fact == "DC형 적립금 운용 주체는 근로자입니다."


def test_negative_claim_supports_db_company_operation_fact():
    stance = resolve_claim_stance("DB는 내가 안 굴리는 거지?", ("DB.operation_party",))

    assert stance.stance == "support"
    assert stance.claim_polarity == "negative"
    assert stance.answer_prefix == "네."


def test_open_operation_party_question_stays_neutral():
    assert resolve_claim_stance("DB 적립금은 누가 운용하나요?", ("DB.operation_party",)).stance == "neutral"


@pytest.mark.parametrize(
    ("question", "requirement", "expected_stance"),
    (
        ("DB는 내가 직접 굴리는 거지?", "DB.operation_party", "contradict"),
        ("DB 내가 운용하는 거 아니야?", "DB.operation_party", "contradict"),
        ("DB는 회사가 굴리는 거 맞지?", "DB.operation_party", "support"),
        ("DC도 회사가 알아서 굴리는 거지?", "DC.operation_party", "contradict"),
        ("DC는 내가 직접 굴리는 거 맞아?", "DC.operation_party", "support"),
        ("DC는 근로자가 운용하는 거 아니었어?", "DC.operation_party", "support"),
    ),
)
def test_db_dc_confirmation_families_have_the_expected_stance(question, requirement, expected_stance):
    assert resolve_claim_stance(question, (requirement,)).stance == expected_stance
