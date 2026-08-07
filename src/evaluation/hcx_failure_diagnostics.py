"""Pure classification helpers for sanitized HCX diagnostic metadata."""


def baseline_failure_ids(rows):
    structured = {
        row["question_id"]
        for row in rows
        if row.get("generator_attempted") and not row.get("generation_model")
    }
    citation = {
        row["question_id"]
        for row in rows
        if row.get("generator_attempted") and row.get("generation_model") and not row.get("generator_called")
    }
    return structured, citation


def classify_structured(diagnostic):
    diagnostic = diagnostic or {}
    status = diagnostic.get("http_status")
    exception = diagnostic.get("exception_type", "")
    finish_reason = str(diagnostic.get("finish_reason") or "").lower()
    tail = str(diagnostic.get("content_tail_shape") or "").rstrip()
    if status and status >= 400 or exception in {"TimeoutError", "URLError", "HTTPError"}:
        return "http_retry", "http_or_transport_failure"
    if "length" in finish_reason or (exception == "JSONDecodeError" and tail and not tail.endswith(("}", "]"))):
        return "truncation", "incomplete_json_tail"
    if diagnostic.get("cited_chunk_ids_present") is False or diagnostic.get("cited_chunk_ids_type") not in {None, "list"}:
        return "citation_format", "citation_field_schema_violation"
    if diagnostic.get("response_envelope_present") is False or diagnostic.get("response_has_result") is False:
        return "http_retry", "response_envelope_mismatch"
    if exception == "JSONDecodeError":
        return "json_format", "malformed_or_wrapped_json"
    return "other", "unclassified_structured_failure"


def classify_citation(diagnostic):
    reason = (diagnostic or {}).get("citation_validation_reason")
    if reason == "missing_citation":
        return "missing_citation"
    if reason == "unknown_chunk_id":
        return "unknown_chunk_id"
    return "other_citation_validation_failure"


def diagnosis_rows(baseline_rows, diagnostic_rows):
    baseline_structured, baseline_citation = baseline_failure_ids(baseline_rows)
    rows = []
    for row in diagnostic_rows:
        if not row.get("generator_attempted"):
            continue
        diagnostic = row.get("generation_diagnostic") or {}
        if not row.get("generation_model"):
            category, subcategory = classify_structured(diagnostic)
            rows.append({
                "question_id": row["question_id"], "failure_group": "structured_output", "category": category,
                "subcategory": subcategory, "failure_stage": row.get("failure_stage"), "http_status": diagnostic.get("http_status"),
                "attempt_count": diagnostic.get("attempt_count"), "retry_used": diagnostic.get("retry_used"),
                "stop_reason": diagnostic.get("finish_reason"), "content_length": diagnostic.get("content_length"),
                "json_parse_success": diagnostic.get("json_parse_success", False), "exception_type": diagnostic.get("exception_type") or row.get("generation_error"),
                "exception_message": diagnostic.get("exception_message"), "evidence": diagnostic, "baseline_target": row["question_id"] in baseline_structured,
                "reproduced": row["question_id"] in baseline_structured,
            })
        elif not row.get("generator_called"):
            rows.append({
                "question_id": row["question_id"], "failure_group": "citation_validation", "category": "citation_validation",
                "subcategory": classify_citation(diagnostic), "failure_stage": row.get("failure_stage"), "http_status": diagnostic.get("http_status"),
                "attempt_count": diagnostic.get("attempt_count"), "retry_used": diagnostic.get("retry_used"),
                "stop_reason": diagnostic.get("finish_reason"), "content_length": diagnostic.get("content_length"),
                "json_parse_success": diagnostic.get("json_parse_success", False), "exception_type": row.get("generation_error"),
                "exception_message": None, "evidence": diagnostic, "baseline_target": row["question_id"] in baseline_citation,
                "reproduced": row["question_id"] in baseline_citation,
            })
    return rows


def baseline_comparison_rows(baseline_rows, unpaced_rows, paced_rows):
    """Attach both diagnostic runs to every failure from the original baseline."""
    baseline_structured, baseline_citation = baseline_failure_ids(baseline_rows)
    unpaced_by_id = {row["question_id"]: row for row in unpaced_rows}
    paced_by_id = {row["question_id"]: row for row in paced_rows}
    rows = []
    for question_id in sorted(baseline_structured | baseline_citation):
        group = "structured_output" if question_id in baseline_structured else "citation_validation"
        unpaced = unpaced_by_id.get(question_id, {})
        paced = paced_by_id.get(question_id, {})
        unpaced_diagnostic = unpaced.get("generation_diagnostic") or {}
        paced_diagnostic = paced.get("generation_diagnostic") or {}
        if group == "structured_output":
            reproduced = bool(unpaced.get("generator_attempted") and not unpaced.get("generation_model"))
            paced_reproduced = bool(paced.get("generator_attempted") and not paced.get("generation_model"))
            if reproduced:
                category, subcategory = classify_structured(unpaced_diagnostic)
                diagnostic = unpaced_diagnostic
            else:
                category, subcategory = "not_reproduced", "accepted_or_different_outcome"
                diagnostic = paced_diagnostic or unpaced_diagnostic
            source_row = unpaced if reproduced else paced
        else:
            category = "citation_validation"
            source_row = paced if paced.get("generator_attempted") and paced.get("generation_model") and not paced.get("generator_called") else unpaced
            diagnostic = (source_row.get("generation_diagnostic") or unpaced_diagnostic)
            subcategory = classify_citation(diagnostic)
            reproduced = bool(unpaced.get("generator_attempted") and unpaced.get("generation_model") and not unpaced.get("generator_called"))
            paced_reproduced = bool(paced.get("generator_attempted") and paced.get("generation_model") and not paced.get("generator_called"))
        rows.append({
            "question_id": question_id,
            "failure_group": group,
            "category": category,
            "subcategory": subcategory,
            "failure_stage": source_row.get("failure_stage"),
            "http_status": diagnostic.get("http_status"),
            "attempt_count": diagnostic.get("attempt_count"),
            "retry_used": diagnostic.get("retry_used"),
            "stop_reason": diagnostic.get("finish_reason"),
            "content_length": diagnostic.get("content_length"),
            "json_parse_success": diagnostic.get("json_parse_success", False),
            "exception_type": diagnostic.get("exception_type") or source_row.get("generation_error"),
            "exception_message": diagnostic.get("exception_message"),
            "evidence": {"unpaced": unpaced_diagnostic, "paced": paced_diagnostic},
            "reproduced": reproduced,
            "paced_reproduced": paced_reproduced,
            "paced_outcome": "accepted" if paced.get("generator_called") else paced.get("generation_error") or paced.get("failure_stage"),
        })
    return rows
