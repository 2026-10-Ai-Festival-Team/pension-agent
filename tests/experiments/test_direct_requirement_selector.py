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
