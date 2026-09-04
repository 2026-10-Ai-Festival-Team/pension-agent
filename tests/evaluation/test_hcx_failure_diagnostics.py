from src.evaluation.hcx_failure_diagnostics import baseline_comparison_rows, classify_citation, classify_structured, diagnosis_rows


def test_classifies_truncated_json_tail_without_raw_content():
    category, subcategory = classify_structured(
        {"exception_type": "JSONDecodeError", "content_tail_shape": '{"xxxxxxxx": "xxxxxxxx"'}
    )

    assert (category, subcategory) == ("truncation", "incomplete_json_tail")


def test_classifies_citation_field_and_http_failures_separately():
    assert classify_structured({"cited_chunk_ids_present": False})[0] == "citation_format"
    assert classify_structured({"http_status": 429})[0] == "http_retry"
    assert classify_citation({"citation_validation_reason": "unknown_chunk_id"}) == "unknown_chunk_id"


def test_diagnosis_marks_baseline_question_reproduction():
    baseline = [{"question_id": "R-001", "generator_attempted": True, "generation_model": None}]
    diagnostic = [{"question_id": "R-001", "generator_attempted": True, "generation_model": None, "generation_diagnostic": {"exception_type": "JSONDecodeError", "content_tail_shape": "{"}}]

    rows = diagnosis_rows(baseline, diagnostic)

    assert rows[0]["reproduced"] is True
    assert rows[0]["category"] == "truncation"


def test_comparison_keeps_rate_limited_and_paced_results_separate():
    baseline = [{"question_id": "R-001", "generator_attempted": True, "generation_model": None}]
    unpaced = [{"question_id": "R-001", "generator_attempted": True, "generation_model": None, "generation_diagnostic": {"http_status": 429, "exception_type": "HTTPError"}}]
    paced = [{"question_id": "R-001", "generator_attempted": True, "generator_called": True, "generation_model": "HCX", "generation_diagnostic": {"http_status": 200}}]

    rows = baseline_comparison_rows(baseline, unpaced, paced)

    assert rows[0]["category"] == "http_retry"
    assert rows[0]["reproduced"] is True
    assert rows[0]["paced_reproduced"] is False
