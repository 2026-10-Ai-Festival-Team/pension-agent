from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.required_fact_completeness import RequiredFactCompletenessGate


def _context(text: str) -> SearchResult:
    return SearchResult(
        rank=1, chunk_id="chunk", score=1.0, text=text, source_id="source",
        source_path="doc.pdf", source_format="pdf", document_type="guide",
        locator=ChunkLocator(page_start=1, page_end=1), element_ids=["element"],
    )


def test_historical_risk_contract_requires_before_after_and_reason_from_selected_evidence():
    gate = RequiredFactCompletenessGate()
    context = _context("변경전 위험등급 1등급 | 변경후 위험등급 3등급 | 위험등급 변경사유 분류체계 개편")

    incomplete = gate.assess(["product.risk_grade.historical"], [context], "현재 위험등급은 2등급입니다.")
    complete = gate.assess(
        ["product.risk_grade.historical"], [context],
        "변경 전 위험등급은 1등급, 변경 후 위험등급은 3등급이며 변경 사유는 분류체계 개편입니다.",
    )

    assert incomplete.evidence_contract_valid is True
    assert set(incomplete.missing_fact_keys) == {
        "risk_history_before_grade", "risk_history_after_grade", "risk_history_reason",
    }
    assert complete.missing_fact_keys == ()


def test_irp_tax_contract_requires_deferral_receipt_and_distribution_from_selected_evidence():
    gate = RequiredFactCompletenessGate()
    context = _context("운용수익 과세: 연금 수령 시까지 과세이연, 운용 중 세금 없음. 세금납부시점: 연금 수령시마다 분산.")

    incomplete = gate.assess(["retirement_income.IRP_transfer.tax_timing"], [context], "연금 수령 시 과세됩니다.")
    complete = gate.assess(
        ["retirement_income.IRP_transfer.tax_timing"], [context],
        "운용 중에는 과세이연되고, 연금 수령 때 과세되며 수령 시마다 분산해 납부합니다.",
    )

    assert incomplete.evidence_contract_valid is True
    assert set(incomplete.missing_fact_keys) == {"irp_tax_deferral", "irp_tax_payment_distributed"}
    assert complete.missing_fact_keys == ()


def test_uncontracted_requirement_does_not_add_a_new_fact_gate():
    assessment = RequiredFactCompletenessGate().assess(["DC.employer_contribution"], [_context("연간 임금총액의 1/12 이상")], "")

    assert assessment.applicable is False
    assert assessment.missing_fact_keys == ()


def test_host_completion_extracts_only_the_missing_irp_timing_fact_from_selected_evidence():
    gate = RequiredFactCompletenessGate()
    context = _context(
        "운용수익 과세 | 연금 수령 시까지 과세이연(운용 중 세금 없음)\n"
        "세금납부시점 | 연금 수령시마다 분산"
    )
    completion = gate.complete_missing_facts(
        ["retirement_income.IRP_transfer.tax_timing"], [context],
        "운용수익은 연금 수령 시까지 과세이연되어 운용 중 세금이 없고, 연금 수령 시 과세됩니다.",
    )

    assert completion.completed_fact_keys == ("irp_tax_payment_distributed",)
    assert completion.unresolved_fact_keys == ()
    assert completion.supporting_chunk_ids == ("chunk",)
    assert completion.text == "세금 납부는 연금 수령 시마다 분산됩니다."


def test_host_completion_never_creates_a_fragment_without_an_exact_selected_evidence_contract():
    gate = RequiredFactCompletenessGate()
    completion = gate.complete_missing_facts(
        ["retirement_income.IRP_transfer.tax_timing"], [_context("과세이연")], "",
    )

    assert completion.text == ""
    assert completion.completed_fact_keys == ()
    assert completion.unresolved_fact_keys == (
        "irp_tax_deferral", "irp_tax_at_pension_receipt", "irp_tax_payment_distributed",
    )


def test_host_completion_adds_isa_rate_and_cap_only_when_both_are_in_selected_evidence():
    gate = RequiredFactCompletenessGate()
    context = _context("ISA 전환금액의 10%를 300만 원 한도로 추가 세액공제합니다.")
    completion = gate.complete_missing_facts(["ISA.transfer.additional_tax_credit"], [context], "")

    assert completion.completed_fact_keys == (
        "isa_transfer_additional_credit_rate", "isa_transfer_additional_credit_cap",
    )
    assert completion.unresolved_fact_keys == ()
    assert completion.supporting_chunk_ids == ("chunk",)
    assert "10%" in completion.text and "300만원" in completion.text


def test_host_completion_can_supply_only_explicit_dc_benefit_and_pension_savings_facts():
    gate = RequiredFactCompletenessGate()
    dc = _context("DC 퇴직급여 산정은 부담금 누계액 ± 운용손익입니다.")
    savings = _context("연금저축 인출은 부득이한 사유를 확인합니다.")

    dc_completion = gate.complete_missing_facts(["DC.benefit_determination"], [dc], "")
    savings_completion = gate.complete_missing_facts(["pension_savings.early_withdrawal.allowed_reasons"], [savings], "")

    assert set(dc_completion.completed_fact_keys) == {"dc_benefit_contribution", "dc_benefit_investment_return"}
    assert "부담금" in dc_completion.text and "운용손익" in dc_completion.text
    assert savings_completion.completed_fact_keys == ("pension_savings_early_withdrawal_compelling_reason",)
    assert "부득이한 사유" in savings_completion.text


def test_host_completion_adds_irp_legal_grounds_only_when_direct_legal_rule_is_selected():
    gate = RequiredFactCompletenessGate()
    direct = _context("IRP는 근퇴법의 적용을 받으며 중도인출 사유를 법으로 열거하고 있습니다.")

    assessment = gate.assess(["IRP.early_withdrawal.allowed_reasons"], [direct], "가능한 사유가 있습니다.")
    completion = gate.complete_missing_facts(["IRP.early_withdrawal.allowed_reasons"], [direct], "가능한 사유가 있습니다.")

    assert assessment.evidence_contract_valid is True
    assert assessment.missing_fact_keys == ("irp_early_withdrawal_legal_grounds",)
    assert completion.completed_fact_keys == ("irp_early_withdrawal_legal_grounds",)
    assert completion.supporting_chunk_ids == ("chunk",)
    assert "법정사유" in completion.text


def test_irp_legal_grounds_contract_never_completes_from_reason_list_alone():
    completion = RequiredFactCompletenessGate().complete_missing_facts(
        ["IRP.early_withdrawal.allowed_reasons"],
        [_context("IRP 중도인출 사유: 주택 구입, 요양, 파산")],
        "",
    )

    assert completion.completed_fact_keys == ()
    assert completion.text == ""


def test_dc_early_withdrawal_document_contract_requires_document_not_generic_proof():
    gate = RequiredFactCompletenessGate()
    context = _context("DC 중도인출은 필요한 증빙서류를 구비해 회사에 제출합니다.")

    generic_proof = gate.assess(
        ["DC.early_withdrawal.required_documents"], [context],
        "DC 중도인출에서는 법정사유별로 증빙이 필요합니다.",
    )
    document_complete = gate.assess(
        ["DC.early_withdrawal.required_documents"], [context],
        "DC 중도인출에서는 법정사유별로 필요한 증빙서류를 준비해야 합니다.",
    )

    assert generic_proof.evidence_contract_valid is True
    assert generic_proof.missing_fact_keys == ("dc_early_withdrawal_document_requirement",)
    assert document_complete.missing_fact_keys == ()


def test_dc_early_withdrawal_host_completion_uses_only_selected_evidence_backed_document_requirement():
    gate = RequiredFactCompletenessGate()
    direct = _context("DC 중도인출은 상황에 맞는 증빙서류를 구비해 제출합니다.")
    generic_only = _context("DC 중도인출에서 사유별 증빙이 필요합니다.")

    completion = gate.complete_missing_facts(
        ["DC.early_withdrawal.required_documents"], [direct],
        "DC 중도인출에서는 법정사유별로 증빙이 필요합니다.",
    )
    no_completion = gate.complete_missing_facts(
        ["DC.early_withdrawal.required_documents"], [generic_only],
        "DC 중도인출에서는 법정사유별로 증빙이 필요합니다.",
    )

    assert completion.completed_fact_keys == ("dc_early_withdrawal_document_requirement",)
    assert completion.supporting_chunk_ids == ("chunk",)
    assert completion.text == "DC 중도인출은 법정사유별로 필요한 증빙서류를 준비해야 합니다."
    assert no_completion.completed_fact_keys == ()
    assert no_completion.text == ""


def test_dc_early_withdrawal_completion_never_invents_document_names_or_expands_to_irp_facts():
    gate = RequiredFactCompletenessGate()
    context = _context("DC 중도인출은 필요한 증빙서류를 구비해 제출합니다.")
    completion = gate.complete_missing_facts(
        ["DC.early_withdrawal.required_documents"], [context], "",
    )

    assert "진단서" not in completion.text
    assert "IRP" not in completion.text
    assert completion.text == "DC 중도인출은 법정사유별로 필요한 증빙서류를 준비해야 합니다."


def test_host_completion_distinguishes_tax_deferral_from_tax_exemption_using_selected_evidence():
    gate = RequiredFactCompletenessGate()
    contexts = [
        _context("운용 기간별 과세이연 O와 과세이연 X를 비교합니다."),
        _context("연금계좌 수익은 연금수령 시 연금소득으로 분리과세 됩니다."),
    ]

    completion = gate.complete_missing_facts(
        ["pension_account.investment_income.tax_timing", "pension_account.investment_income.not_tax_exempt"], contexts, ""
    )

    assert set(completion.completed_fact_keys) == {
        "pension_account_investment_income_deferral", "pension_account_investment_income_not_exempt",
    }
    assert "과세이연" in completion.text and "면세가 아니라" in completion.text
