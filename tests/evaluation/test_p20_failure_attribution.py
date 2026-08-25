from src.evaluation.p20_failure_attribution import summarize


def _row(question_id, *, called=False, attempted=True, error=None, history=None):
    return {
        "question_id": question_id,
        "answerable": True,
        "generator_attempted": attempted,
        "generator_called": called,
        "generation_model": "HCX" if called else None,
        "generation_error": error,
        "generation_attempt_history": history or [],
    }


def _review(question_id, *, strict=False, eligibility="generated_answer"):
    return {
        "question_id": question_id,
        "review_eligibility": eligibility,
        "review": {
            "factual_correctness": "pass" if strict else "fail",
            "requirement_coverage": "pass" if strict else "fail",
            "evidence_grounding": "pass" if strict else "fail",
        },
    }


def test_p20_attribution_keeps_provider_and_semantic_failures_separate():
    rows = [
        _row("A", called=True),
        _row("B", error="GenerationError", history=[{"http_status": 429}]),
        _row("C", called=True, history=[{"http_status": 429}]),
        _row("D", attempted=False),
    ]
    reviews = {
        "A": _review("A", strict=True),
        "B": _review("B", eligibility="generation_or_citation_rejection"),
        "C": _review("C", strict=False),
        "D": _review("D", eligibility="evidence_policy_rejection"),
    }

    result = summarize(rows, reviews)

    assert result["unconditional_strict_e2e"] == {"useful": 1, "denominator": 4, "rate": 0.25}
    assert result["provider_successfully_evaluable"]["denominator"] == 3
    assert result["provider_successfully_evaluable"]["useful"] == 1
    assert result["normal_hcx_semantic"]["semantic_failure_question_ids"] == ["C"]
    assert result["provider_incident"]["provider_retry_exhaustion_question_ids"] == ["B"]
