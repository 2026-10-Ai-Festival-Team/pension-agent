import pytest

from src.experiments.semantic_contract_v2 import (
    RequirementComposerV2,
    SemanticContractV2Validator,
    SemanticPlanV2,
    SemanticRelation,
)


def test_action_is_deterministically_implied_by_early_withdrawal_fields() -> None:
    plan = SemanticPlanV2(
        subjects=("account:DC",),
        fields=("withdrawal_reason", "required_document"),
        qualifiers=("before_retirement",),
    )

    assert RequirementComposerV2.compose(plan) == (
        "account:DC.early_withdrawal.allowed_reason",
        "account:DC.early_withdrawal.required_document",
    )


def test_v2_separates_partial_withdrawal_from_account_closure() -> None:
    plan = SemanticPlanV2(
        subjects=("account:pension",),
        fields=("partial_withdrawal_condition", "account_closure_condition", "partial_withdrawal_tax", "account_closure_tax"),
        qualifiers=(),
        relations=(SemanticRelation("comparison", left="partial_withdrawal", right="account_closure"),),
    )

    requirements = RequirementComposerV2.compose(plan)

    assert "account:pension.partial_withdrawal.condition" in requirements
    assert "account:pension.account_closure.tax_treatment" in requirements
    assert "relation.comparison.partial_withdrawal<->account_closure" in requirements


def test_v2_keeps_current_and_historical_risk_grade_distinct() -> None:
    plan = SemanticPlanV2(
        subjects=("product:KR5120420039", "product:KR5120420091"),
        fields=("risk_grade",),
        qualifiers=("current", "historical"),
    )

    assert RequirementComposerV2.compose(plan) == (
        "product:KR5120420039+product:KR5120420091.risk_grade.current",
        "product:KR5120420039+product:KR5120420091.risk_grade.historical",
    )


def test_v2_represents_isa_maturity_and_additional_credit_without_action_atom() -> None:
    plan = SemanticPlanV2(
        subjects=("account:ISA", "account:pension"),
        fields=("transfer_deadline", "tax_credit_limit"),
        qualifiers=("isa_maturity", "additional_credit"),
        relations=(SemanticRelation("transfer", source="account:ISA", destination="account:pension"),),
    )

    requirements = RequirementComposerV2.compose(plan)

    assert "account:ISA+account:pension.transfer_deadline" in requirements
    assert "account:ISA+account:pension.tax_credit_limit" in requirements
    assert "relation.transfer.account:ISA->account:pension" in requirements


def test_v2_represents_transfer_tax_timing_as_a_distinct_evidence_scope() -> None:
    plan = SemanticPlanV2(
        subjects=("account:IRP",),
        fields=("tax_timing",),
        qualifiers=("tax_timing_on_transfer",),
        relations=(SemanticRelation("transfer", source="event:retirement_benefit", destination="account:IRP"),),
    )

    assert RequirementComposerV2.compose(plan) == (
        "account:IRP.transfer.tax_timing",
        "relation.transfer.event:retirement_benefit->account:IRP",
    )


def test_v2_rejects_unknown_values() -> None:
    plan = SemanticPlanV2(subjects=("account:DC",), fields=("unknown_field",), qualifiers=())

    assert SemanticContractV2Validator.validate(plan) == ("field:unknown_field",)
    with pytest.raises(ValueError, match="unknown_field"):
        RequirementComposerV2.compose(plan)
