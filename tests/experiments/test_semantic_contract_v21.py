from src.experiments.semantic_contract_v21 import (
    DirectionalTransfer,
    RequirementComposerV21,
    SemanticPlanV21,
    has_comparison_intent,
)


def test_v21_derives_generic_comparison_without_model_relation() -> None:
    plan = SemanticPlanV21(("account:DB", "account:DC"), ("operation_party",), (), ())

    assert has_comparison_intent("DB와 DC는 누가 운용하는지 비교해줘", plan) is True
    assert "relation.comparison.account:DB+account:DC<->account:DB+account:DC" in RequirementComposerV21.compose("DB와 DC는 누가 운용하는지 비교해줘", plan)


def test_v21_preserves_directional_transfer_and_does_not_treat_scope_as_alias() -> None:
    plan = SemanticPlanV21(
        ("account:ISA", "account:pension"), ("transfer_deadline", "tax_timing"),
        ("isa_maturity", "tax_timing_on_transfer"),
        (DirectionalTransfer("account:ISA", "account:pension"),),
    )
    requirements = RequirementComposerV21.compose("ISA 만기 자금을 연금계좌로 옮길 때 과세 시점과 기한", plan)

    assert "relation.transfer.account:ISA->account:pension" in requirements
    assert "account:ISA+account:pension.transfer.tax_timing" in requirements


def test_v21_derives_partial_vs_closure_comparison_with_single_account() -> None:
    plan = SemanticPlanV21(
        ("account:pension",), ("partial_withdrawal_condition", "account_closure_condition"), (), (),
    )

    assert has_comparison_intent("일부만 빼는 것과 계좌를 끝내는 것은 어떻게 다른가요?", plan) is True
