from src.evaluation.policy_regression import summarize_policy_regression


def test_policy_regression_summary_separates_provenance_from_existing_gate_behavior():
    summary = summarize_policy_regression(
        [
            {
                "provenance_false_rejection": False,
                "augmented_only_unsafe_pass": False,
                "expected_rejection_missed": False,
                "intent": "pension_system",
                "is_general_system_question": True,
                "tax_notice_present": False,
                "general_notice_unnecessary": True,
                "recommendation_clarification": False,
                "current_sufficient": True,
                "citation_is_primary_original": True,
            },
            {
                "provenance_false_rejection": True,
                "augmented_only_unsafe_pass": False,
                "expected_rejection_missed": False,
                "intent": "tax",
                "is_general_system_question": False,
                "tax_notice_present": True,
                "general_notice_unnecessary": False,
                "recommendation_clarification": False,
                "current_sufficient": True,
                "citation_is_primary_original": True,
            },
        ]
    )

    assert summary["questions"] == 2
    assert summary["provenance_false_rejection"] == 1
    assert summary["tax_notice_missing"] == 0
    assert summary["general_notice_regression"] == 0
