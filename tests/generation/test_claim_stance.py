from src.generation.claim_stance import resolve_claim_stance


def test_db_worker_confirmation_is_contradicted_by_db_operation_party_requirement():
    stance = resolve_claim_stance("DB는 내가 직접 굴리는 거지?", ("DB.operation_party",))

    assert stance.stance == "contradict"
    assert stance.answer_prefix == "아니요."
    assert stance.apply_answer_prefix("네, 맞습니다. DB형 적립금의 운용 주체는 회사입니다.") == (
        "아니요. DB형 적립금의 운용 주체는 회사입니다."
    )


def test_dc_company_confirmation_is_contradicted_by_dc_operation_party_requirement():
    stance = resolve_claim_stance("DC는 회사가 직접 굴리는 거죠?", ("DC.operation_party",))

    assert stance.stance == "contradict"
    assert stance.supported_fact == "DC형 적립금 운용 주체는 근로자입니다."


def test_open_operation_party_question_and_negated_claim_stay_neutral():
    assert resolve_claim_stance("DB 적립금은 누가 운용하나요?", ("DB.operation_party",)).stance == "neutral"
    assert resolve_claim_stance("DB는 내가 직접 운용하는 제도가 아니지?", ("DB.operation_party",)).stance == "neutral"
