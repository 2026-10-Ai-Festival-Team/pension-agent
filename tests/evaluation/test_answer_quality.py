from src.evaluation.answer_quality import build_review_packet, summarize_review_packet
from src.evaluation.retrieval_dataset import RetrievalQuestion


def question(answerable=True, requirement="any"):
    return RetrievalQuestion("R-001", "dev", "질문", "tax", answerable, False, [], [], [], ["근거"], requirement, [])


def row(answerable=True, called=True):
    return {
        "question_id": "R-001", "answerable": answerable, "status_code": 200,
        "answer": "답변", "retrieved_context": "[gold] 근거", "retrieved_chunk_ids": ["gold"],
        "cited_chunk_ids": ["gold"], "generator_attempted": called, "generator_called": called,
        "citation_valid": called, "generation_error": None, "failure_stage": "success",
        "direct_evidence_hit_at_10": True, "all_relevant_evidence_hit_at_10": None,
    }


def test_review_packet_keeps_answer_and_retrieval_dimensions_separate():
    packet = build_review_packet([row()], [question()], "run-hash")

    assert packet[0]["review_eligibility"] == "generated_answer"
    assert packet[0]["answer"] == "답변"
    assert packet[0]["system"]["direct_evidence_hit_at_10"] is True
    assert packet[0]["review"]["factual_correctness"] == "not_reviewed"


def test_unsupported_question_is_a_policy_review_not_a_generation_failure():
    packet = build_review_packet([row(answerable=False, called=False)], [question(answerable=False)], "run-hash")

    assert packet[0]["review_eligibility"] == "unsupported_or_personal_policy"
    assert packet[0]["review"]["information_limit_handling"] == "not_reviewed"


def test_summary_does_not_treat_pending_manual_labels_as_quality_scores():
    summary = summarize_review_packet(build_review_packet([row()], [question()], "run-hash"))

    assert summary["automated"]["direct_evidence_hit_at_10"] == 1
    assert summary["manual"]["reviewed_answer_count"] == 0
