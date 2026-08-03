from scripts.analyze_retrieval_failures import analysis_flags, should_analyze
from src.evaluation.retrieval_dataset import RetrievalQuestion


def make_question(evidence_requirement: str = "any") -> RetrievalQuestion:
    return RetrievalQuestion(
        question_id="R-test",
        split="dev",
        question="질문",
        category="test",
        answerable=True,
        requires_ocr=False,
        product_codes=[],
        relevant_chunks=[],
        relevant_source_ids=[],
        required_terms=[],
        evidence_requirement=evidence_requirement,
        notes=[],
    )


def test_analysis_selects_simple_top5_failure():
    flags = analysis_flags(make_question(), simple_rank=6, kiwi_rank=2)

    assert flags["simple_direct_top5_failure"] is True
    assert flags["kiwi_success_simple_failure"] is True
    assert should_analyze(flags) is True


def test_analysis_selects_composite_question_even_when_both_succeed():
    flags = analysis_flags(make_question("all"), simple_rank=1, kiwi_rank=1)

    assert flags["all_evidence_question"] is True
    assert should_analyze(flags) is True


def test_analysis_excludes_non_failure_non_composite_question():
    flags = analysis_flags(make_question(), simple_rank=1, kiwi_rank=1)

    assert should_analyze(flags) is False
