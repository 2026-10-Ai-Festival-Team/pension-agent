"""P25-0에서 provenance와 금융 답변 정책의 회귀를 분리 측정한다."""

from __future__ import annotations

from typing import Iterable

from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResult
from src.orchestration.evidence_assessor import EvidenceAssessor
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.query_analyzer import QueryAnalyzer


def assess_policy_regression(
    *,
    question_id: str,
    question: str,
    expected_rejection: bool,
    retriever: object,
    top_k: int = 10,
) -> dict:
    """HCX 없이 기존 gate와 provenance gate의 차이만 기록한다."""

    analyzer = QueryAnalyzer()
    assessor = EvidenceAssessor()
    policy = FinancialAnswerPolicy()
    analysis = analyzer.analyze(question)
    contexts = retriever.search(analysis.question, top_k=top_k).results
    legacy = assessor.assess_without_provenance(analysis, contexts)
    current = assessor.assess(analysis, contexts)
    primary_contexts = [context for context in contexts if policy.is_primary_original(context)]
    cited = primary_contexts[:1] if current.sufficient else []
    formatted = (
        policy.format_answer("검증용 근거 기반 답변", analysis, cited)
        if current.sufficient
        else policy.format_insufficient(current, analysis)
    )
    cited_are_primary = all(policy.is_primary_original(context) for context in cited)
    general_system_question = analysis.intent == "pension_system" and not analysis.requires_comparison
    return {
        "question_id": question_id,
        "question": question,
        "expected_rejection": expected_rejection,
        "intent": analysis.intent,
        "legacy_sufficient_without_provenance": legacy.sufficient,
        "current_sufficient": current.sufficient,
        "assessment_reason": current.reason,
        "retrieved_chunk_ids": [context.chunk_id for context in contexts],
        "primary_original_context_count": len(primary_contexts),
        "augmented_context_count": sum(
            context.source_type == SourceType.AUGMENTED for context in contexts
        ),
        "provenance_false_rejection": legacy.sufficient and not current.sufficient,
        "augmented_only_unsafe_pass": current.sufficient and not primary_contexts,
        "expected_rejection_missed": expected_rejection and current.sufficient,
        "answer_has_sections": all(marker in formatted for marker in ("[답변]", "[유의사항]")),
        "answer_has_evidence": "[근거]" in formatted,
        "citation_is_primary_original": cited_are_primary,
        "tax_notice_present": analysis.intent == "tax" and "세무전문가" in formatted,
        "is_general_system_question": general_system_question,
        "general_notice_unnecessary": general_system_question and "[유의사항]" not in formatted,
        "recommendation_clarification": (
            analysis.requires_user_conditions
            and "[확인 필요]" in formatted
            and "투자 기간" in formatted
        ),
    }


def provenance_migration_summary(chunks: Iterable[object]) -> dict:
    """기존 JSONL이 default provenance를 안전하게 얻었는지 확인한다."""

    chunks = list(chunks)
    original_primary = sum(
        chunk.source_type == SourceType.ORIGINAL
        and chunk.authority_level == AuthorityLevel.PRIMARY
        for chunk in chunks
    )
    invalid = sum(
        (chunk.source_type == SourceType.ORIGINAL and chunk.authority_level != AuthorityLevel.PRIMARY)
        or (chunk.source_type == SourceType.AUGMENTED and chunk.authority_level == AuthorityLevel.PRIMARY)
        for chunk in chunks
    )
    return {
        "chunk_count": len(chunks),
        "original_primary_count": original_primary,
        "augmented_count": sum(chunk.source_type == SourceType.AUGMENTED for chunk in chunks),
        "invalid_provenance_combinations": invalid,
    }


def summarize_policy_regression(rows: Iterable[dict]) -> dict:
    rows = list(rows)
    return {
        "questions": len(rows),
        "provenance_false_rejection": sum(row["provenance_false_rejection"] for row in rows),
        "augmented_only_unsafe_pass": sum(row["augmented_only_unsafe_pass"] for row in rows),
        "expected_rejection_missed": sum(row["expected_rejection_missed"] for row in rows),
        "tax_notice_missing": sum(
            row["intent"] == "tax" and not row["tax_notice_present"] for row in rows
        ),
        "general_notice_regression": sum(
            row["is_general_system_question"] and not row["general_notice_unnecessary"]
            for row in rows
        ),
        "recommendation_clarification_missing": sum(
            row["intent"] == "conditional_recommendation"
            and not row["recommendation_clarification"]
            for row in rows
        ),
        "non_primary_citation": sum(
            row["current_sufficient"] and not row["citation_is_primary_original"]
            for row in rows
        ),
    }
