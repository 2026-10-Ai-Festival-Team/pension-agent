from src.evaluation.corpus_coverage_audit import coverage_owner, owner_counts


def test_coverage_owner_follows_the_source_to_retrieval_order() -> None:
    assert coverage_owner(
        raw_evidence_exists=False,
        corpus_evidence_exists=False,
        semantic_evidence_in_candidates=False,
        selected_evidence_supports_requirement=False,
    ) == "true_data_gap"
    assert coverage_owner(
        raw_evidence_exists=True,
        corpus_evidence_exists=False,
        semantic_evidence_in_candidates=False,
        selected_evidence_supports_requirement=False,
    ) == "parsing_or_ocr_gap"
    assert coverage_owner(
        raw_evidence_exists=True,
        corpus_evidence_exists=True,
        semantic_evidence_in_candidates=False,
        selected_evidence_supports_requirement=False,
    ) == "retrieval_recall"
    assert coverage_owner(
        raw_evidence_exists=True,
        corpus_evidence_exists=True,
        semantic_evidence_in_candidates=True,
        selected_evidence_supports_requirement=False,
    ) == "evidence_matcher"


def test_owner_counts_include_zeroes() -> None:
    assert owner_counts([{"primary_owner": "retrieval_recall"}]) == {
        "evidence_matcher": 0,
        "parsing_or_ocr_gap": 0,
        "retrieval_recall": 1,
        "selection": 0,
        "true_data_gap": 0,
    }
