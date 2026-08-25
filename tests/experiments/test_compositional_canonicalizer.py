from src.experiments.compositional_canonicalizer import CompositionalParser, RequirementComposer
from src.experiments.compositional_evaluator import evaluate


def test_composes_all_fields_for_a_multi_requirement_dc_withdrawal_question() -> None:
    atoms = CompositionalParser().parse("DC 적립금을 퇴직 전에 일부 꺼내려면 어떤 사유가 되고 무슨 서류를 내야 하나요?")

    assert set(atoms.subjects) == {"account:DC"}
    assert "withdraw" in atoms.actions
    assert {"withdrawal_reason", "required_document"} <= set(atoms.fields)
    assert "before_retirement" in atoms.modifiers
    assert len(RequirementComposer.compose(atoms)) == len(atoms.fields)


def test_product_grade_changeability_is_not_collapsed_into_current_grade() -> None:
    atoms = CompositionalParser().parse("KR510902773M의 위험 분류가 시장 상황에 따라 조정될 가능성이 있나요?")

    assert set(atoms.subjects) == {"product:KR510902773M"}
    assert {"risk_grade", "risk_grade_changeability"} <= set(atoms.fields)
    assert "change_possibility" in atoms.modifiers


def test_unseen_sibling_phrasing_composes_withdrawal_reason_and_document_atoms() -> None:
    atoms = CompositionalParser().parse(
        "DC 가입자가 재직 중 목돈이 필요하면 어떤 법정 이유에서 인출할 수 있고 입증 문서는 무엇이 필요한가요?"
    )

    assert set(atoms.subjects) == {"account:DC"}
    assert "withdraw" in atoms.actions
    assert {"withdrawal_reason", "required_document"} <= set(atoms.fields)
    assert "before_retirement" in atoms.modifiers


def test_evaluator_compares_canonical_sets_and_reports_component_metrics() -> None:
    result = evaluate()

    assert result["candidate_agent_changed"] is False
    assert result["question_count"] == 30
    assert set(result["component_metrics"]) == {"subjects", "actions", "fields", "modifiers"}
    assert result["requirement_composition"]["total"] == 30
