from src.evaluation.citation_contract import classify_citation_failure


def test_citation_failure_classification_does_not_apply_fuzzy_mapping():
    allowed = ["abc123-paragraph-456"]

    assert classify_citation_failure(["abc123-paragraph-456"], allowed, ["abc123"]) is None
    assert classify_citation_failure(["abc123"], allowed, ["abc123"]) == "source_like_identifier"
    assert classify_citation_failure(["abc123-paragraph"], allowed, ["abc123"]) == "truncated_chunk_id"
    assert classify_citation_failure([], allowed, ["abc123"]) == "empty_citation"
    assert classify_citation_failure(None, allowed, ["abc123"]) == "missing_citation"
