import json
from pathlib import Path

from src.config.generation import GenerationSettings
from src.experiments.direct_requirement_selector import (
    DIRECT_REQUIREMENTS,
    DirectRequirementSelectorPromptBuilder,
    HCXDirectRequirementSelector,
    requirements_for_active_subject,
    resolve_product_codes,
)
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.direct_requirement_selector_evaluator import score_requirement_predictions, score_scope_errors


class Transport:
    def __init__(self, content):
        self.content = content

    def post(self, *_args):
        return 200, json.dumps({"result": {"message": {"content": json.dumps(self.content)}}})


def _config():
    return GenerationSettings(generator_backend="hcx", hcx_api_key="test", hcx_model="HCX-007", hcx_base_url="https://example", max_retries=0, hcx_min_interval_seconds=0)


def test_direct_selector_uses_closed_multi_label_enum_and_deterministic_product_resolution():
    schema = DirectRequirementSelectorPromptBuilder().payload("KR510902773M 위험등급", "HCX-007")["responseFormat"]["schema"]

    assert schema["properties"]["selected_requirements"]["items"]["enum"] == list(DIRECT_REQUIREMENTS)
    assert resolve_product_codes("kr510902773m와 KR5127450215") == ("KR510902773M", "KR5127450215")


def test_subject_filtered_catalog_excludes_out_of_scope_requirements_at_schema_level():
    allowed = requirements_for_active_subject("IRP")
    schema = DirectRequirementSelectorPromptBuilder().payload(
        "두 번째 계좌의 인출 과세", "HCX-007", allowed_requirements=allowed, active_subjects=("IRP",),
    )["responseFormat"]["schema"]

    assert "IRP.withdrawal.tax_treatment" in allowed
    assert "pension_savings.withdrawal.tax_treatment" not in allowed
    assert schema["properties"]["selected_requirements"]["items"]["enum"] == list(allowed)


def test_selector_contract_keeps_db_formula_and_product_fee_dimensions_distinct():
    payload = DirectRequirementSelectorPromptBuilder().payload(
        "DB형 퇴직급여 계산식과 상품 연간 총보수는?", "HCX-007"
    )
    prompt = payload["messages"][0]["content"]

    assert "퇴직급여 산식·계산 방식" in prompt
    assert "product.total_fee" in prompt
    assert "product.period_cost" in prompt
    assert "distinct" in prompt


def test_resolver_first_selector_does_not_call_hcx_for_nonunique_scope():
    class FailingSelector:
        def select(self, *_args, **_kwargs):
            raise AssertionError("selector must not run with non-unique scope")

    result = ResolverFirstScopedSelector(FailingSelector()).select(
        "DB와 DC 가운데 가입자가 직접 운용방법을 정하는 쪽의 퇴직급여 금액은 무엇으로 정해지나요?"
    )

    assert result.status == "unresolved_scope"
    assert result.reason == "non_unique_active_subject"


def test_direct_selector_validates_a_multi_requirement_response_without_access_to_product_identity_from_hcx():
    result = HCXDirectRequirementSelector(
        config=_config(),
        transport=Transport({"selected_requirements": ["DC.early_withdrawal.allowed_reasons", "DC.early_withdrawal.required_documents"], "unresolved": False}),
    ).select("DC에서 퇴직 전 일부를 빼려면 어떤 경우고 서류는 무엇인가요?")

    assert result.schema_valid is True
    assert result.ontology_valid is True
    assert result.selected_requirements == ("DC.early_withdrawal.allowed_reasons", "DC.early_withdrawal.required_documents")
    assert result.resolved_product_codes == ()


def test_confirmation_uncertainty_keeps_db_operation_requirement_even_if_hcx_selects_none():
    allowed = requirements_for_active_subject("DB")
    result = HCXDirectRequirementSelector(
        config=_config(),
        transport=Transport({"selected_requirements": [], "unresolved": True}),
    ).select(
        "DB는 내가 직접 굴리는 거 맞지? 아닌가?",
        allowed_requirements=allowed,
        active_subjects=("DB",),
    )

    assert result.selected_requirements == ("DB.operation_party",)
    assert result.unresolved is False
    assert result.diagnostic["confirmation_normalization"]["proposition_core"] == "DB는 내가 직접 굴리는 거"
    assert result.diagnostic["deterministic_confirmation_requirements"] == ["DB.operation_party"]


def test_dc_contribution_floor_alias_resolves_a_contradictory_unresolved_selector_response():
    allowed = requirements_for_active_subject("DC")
    selector = HCXDirectRequirementSelector(
        config=_config(), transport=Transport({"selected_requirements": [], "unresolved": True}),
    )
    for question in (
        "DC형 사용자의 연간 부담금 하한을 숫자로 알려주세요.",
        "DC 부담금의 최소 기준은 얼마인가요?",
        "DC형 사용자 부담금은 연간 임금의 12분의 1 이상인가요?",
    ):
        result = selector.select(question, allowed_requirements=allowed, active_subjects=("DC",))
        assert result.selected_requirements == ("DC.employer_contribution",)
        assert result.unresolved is False
        assert result.diagnostic["deterministic_alias_requirements"] == ["DC.employer_contribution"]


def test_dc_alias_does_not_turn_an_unrelated_query_into_a_requirement():
    result = HCXDirectRequirementSelector(
        config=_config(), transport=Transport({"selected_requirements": [], "unresolved": True}),
    ).select(
        "DC형 가입자 교육은 누가 하나요?",
        allowed_requirements=requirements_for_active_subject("DC"), active_subjects=("DC",),
    )

    assert result.selected_requirements == ()
    assert result.unresolved is True
    assert result.diagnostic["deterministic_alias_requirements"] == []


def test_explicit_field_locks_remove_related_selector_fields_without_widening_scope():
    selector = HCXDirectRequirementSelector(
        config=_config(),
        transport=Transport({"selected_requirements": ["DC.operation_party", "DC.early_withdrawal.allowed_reasons"], "unresolved": False}),
    )
    cases = (
        ("DC형 퇴직급여에 부담금과 운용성과가 함께 반영되나요?", ("DC.benefit_determination",)),
        ("DC 가입자 교육을 외부에 맡길 수 있나요?", ("retirement_pension.participant_education.outsourcing",)),
        ("DC 가입자 교육을 교육기관이나 금융회사에 맡겨도 되는지 궁금합니다.", ("retirement_pension.participant_education.outsourcing",)),
        ("DC 중도인출 때 증빙서류가 필요한가요?", ("DC.early_withdrawal.required_documents",)),
    )
    for question, expected in cases:
        result = selector.select(question, allowed_requirements=requirements_for_active_subject("DC"), active_subjects=("DC",))
        assert result.selected_requirements == expected
        assert result.diagnostic["deterministic_field_lock_requirements"] == list(expected)


def test_field_locks_cover_isa_rate_cap_and_irp_tax_deferral_without_broadening_scope():
    isa = HCXDirectRequirementSelector(
        config=_config(), transport=Transport({"selected_requirements": [], "unresolved": True}),
    ).select(
        "ISA 만기자금 전환 추가 세액공제의 공제율과 최대 금액을 알려주세요.",
        allowed_requirements=requirements_for_active_subject("ISA"), active_subjects=("ISA",),
    )
    irp = HCXDirectRequirementSelector(
        config=_config(), transport=Transport({"selected_requirements": ["pension_account.investment_income.tax_timing"], "unresolved": False}),
    ).select(
        "IRP 운용수익은 비과세가 아니라 과세를 뒤로 미루는 구조인가요?",
        allowed_requirements=requirements_for_active_subject("IRP"), active_subjects=("IRP",),
    )

    assert isa.selected_requirements == ("ISA.transfer.additional_tax_credit",)
    assert irp.selected_requirements == (
        "pension_account.investment_income.tax_timing", "pension_account.investment_income.not_tax_exempt",
    )
    assert "IRP.early_withdrawal.allowed_reasons" not in irp.selected_requirements


def test_irp_catalog_allows_canonical_pension_account_fields_but_not_pension_savings_fields():
    allowed = requirements_for_active_subject("IRP")

    assert "pension_account.partial_withdrawal.condition" in allowed
    assert "pension_account.investment_income.tax_timing" in allowed
    assert "retirement_pension.in_kind_transfer.definition" in allowed
    assert "pension_savings.withdrawal.tax_treatment" not in allowed


def test_irp_in_kind_transfer_definition_lock_overrides_application_route():
    result = HCXDirectRequirementSelector(
        config=_config(),
        transport=Transport({
            "selected_requirements": ["retirement_pension.in_kind_transfer.IRP.application_route"],
            "unresolved": False,
        }),
    ).select(
        "IRP 실물이전은 보유상품을 매도하지 않고 금융회사를 바꾸는 절차인가요?",
        allowed_requirements=requirements_for_active_subject("IRP"),
        active_subjects=("IRP",),
    )

    assert result.selected_requirements == ("retirement_pension.in_kind_transfer.definition",)
    assert result.diagnostic["deterministic_field_lock_requirements"] == ["retirement_pension.in_kind_transfer.definition"]


def test_resolver_first_dc_contribution_floor_reaches_a_selected_frontend_contract():
    result = ResolverFirstScopedSelector(
        HCXDirectRequirementSelector(
            config=_config(), transport=Transport({"selected_requirements": [], "unresolved": True}),
        )
    ).select("DC형 사용자의 연간 부담금 하한을 숫자로 알려주세요.")

    assert result.status == "selected"
    assert result.active_subject == "DC"
    assert result.selection.selected_requirements == ("DC.employer_contribution",)


def test_direct_requirement_evaluator_exposes_multi_requirement_recall_and_extra_requirements():
    rows = [{"source_question_id": "Q-1", "question": "q", "selected_requirements": ["A", "B"]}]
    result = score_requirement_predictions(rows, {"Q-1": ("A", "C")})

    assert result["multi_requirement_recall"] == {"matched": 1, "gold": 2, "recall": 0.5}
    assert result["unsupported_extra_requirement_count"] == 1
    assert result["false_missing_requirement_count"] == 1


def test_direct_requirement_evaluator_accepts_a_fresh_manifest_id_without_a_legacy_source_id():
    rows = [{"id": "P39-2-001", "question": "q", "selected_requirements": ["A"]}]

    result = score_requirement_predictions(rows, {"P39-2-001": ("A",)})

    assert result["requirement_exact"] == {"exact": 1, "total": 1, "accuracy": 1.0}


def test_p39_manual_gold_uses_only_enum_requirements_and_marks_supporting_facts_optional():
    rows = [json.loads(line) for line in Path("question_bank/development/p39_1_direct_requirement_selector_gold.jsonl").read_text(encoding="utf-8").splitlines() if line]

    assert all(requirement in DIRECT_REQUIREMENTS for row in rows for requirement in row["selected_requirements"])
    row = next(row for row in rows if row["source_question_id"] == "P38-2-009")
    assert row["selected_requirements"] == [
        "retirement_pension.in_kind_transfer.DB_DC.application_route",
        "retirement_pension.in_kind_transfer.IRP.application_route",
    ]
    assert row["optional_supporting_requirements"] == ["retirement_pension.in_kind_transfer.definition"]


def test_scope_evaluator_keeps_product_identity_and_scope_failures_separate_from_f1():
    rows = [{"id": "Q-1", "scope_requirements": ["DC.operation_party"], "expected_product_codes": ["KR0000000001"]}]

    result = score_scope_errors(rows, {"Q-1": ("DB.operation_party",)}, {"Q-1": ("KR0000000002",)})

    assert result["scope_error_count"] == 1
    assert result["details"][0]["missing_scope_requirements"] == ["DC.operation_party"]
    assert result["details"][0]["product_scope_error"] is True
