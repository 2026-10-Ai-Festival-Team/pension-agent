from dataclasses import dataclass

from src.generation.base import AnswerGenerator
from src.orchestration.context_builder import ContextBuilder
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.evidence_assessor import EvidenceAssessment, EvidenceAssessor
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.generation.errors import CitationValidationError, GenerationError


@dataclass
class PensionAgent:
    retriever: object
    generator: AnswerGenerator
    analyzer: QueryAnalyzer = QueryAnalyzer()
    context_builder: ContextBuilder = ContextBuilder()
    assessor: EvidenceAssessor = EvidenceAssessor()
    financial_policy: FinancialAnswerPolicy = FinancialAnswerPolicy()

    def answer(self, question: str, top_k: int = 5) -> dict:
        analysis = self.analyzer.analyze(question)
        response = self.retriever.search(analysis.question, top_k=top_k)
        contexts = self.context_builder.build(response.results, top_k)
        assessment = self.assessor.assess(analysis, contexts)
        recommendation = self.financial_policy.recommendation_decision(analysis)
        product_reference = self.financial_policy.product_reference_decision(analysis)

        # 추천성 질의는 retrieval이나 HCX의 행동을 바꾸지 않는다. 다만 사용자에게
        # 단일 상품을 권유하는 경로는 생성 전에 막고, 조건 확인 또는 후보 비교로
        # 명시적으로 전환한다.
        if recommendation.is_recommendation_context:
            if recommendation.missing_conditions:
                answer = self.financial_policy.format_recommendation_clarification(recommendation)
                assessment = EvidenceAssessment(
                    False,
                    "conditional_recommendation_requires_user_conditions",
                    list(recommendation.missing_conditions),
                )
            else:
                answer = self.financial_policy.format_recommendation_comparison_guidance(recommendation)
                assessment = EvidenceAssessment(False, "recommendation_comparison_only")
            trace = {
                "query_type": analysis.intent,
                "normalization": "pension-v1",
                "retrieved_chunk_ids": [item.chunk_id for item in contexts],
                "evidence_sufficient": assessment.sufficient,
                "assessment_reason": assessment.reason,
                "generator": type(self.generator).__name__,
                "generator_attempted": False,
                "generator_called": False,
                "cited_chunk_ids": [],
                "generation_error": None,
                "financial_policy": {
                    "recommendation_context": True,
                    "profile_complete": recommendation.profile_complete,
                    "reasons": list(recommendation.reasons),
                },
            }
            return {
                "question": analysis.question,
                "retrieved_context": contexts,
                "think_trace": trace,
                "answer": answer,
            }
        if product_reference.requires_product_identification:
            trace = {
                "query_type": analysis.intent,
                "normalization": "pension-v1",
                "retrieved_chunk_ids": [item.chunk_id for item in contexts],
                "evidence_sufficient": False,
                "assessment_reason": "product_identification_required",
                "generator": type(self.generator).__name__,
                "generator_attempted": False,
                "generator_called": False,
                "cited_chunk_ids": [],
                "generation_error": None,
                "financial_policy": {
                    "recommendation_context": False,
                    "profile_complete": False,
                    "reasons": ["product_identification_required"],
                },
            }
            return {
                "question": analysis.question,
                "retrieved_context": contexts,
                "think_trace": trace,
                "answer": self.financial_policy.format_product_reference_clarification(),
            }
        generator_attempted = assessment.sufficient
        generator_called = generator_attempted
        generated = None
        generation_error = None
        generation_diagnostic = None
        try:
            generated = self.generator.generate(question=analysis.question, contexts=contexts, query_analysis=analysis) if generator_called else None
            if generated:
                generation_diagnostic = generated.diagnostic
                allowed_ids = {item.chunk_id for item in contexts}
                unknown_ids = sorted(set(generated.cited_chunk_ids) - allowed_ids)
                if not generated.cited_chunk_ids or unknown_ids:
                    reason = "missing_citation" if not generated.cited_chunk_ids else "unknown_chunk_id"
                    raise CitationValidationError(
                        "invalid citations",
                        diagnostic={
                            **(generation_diagnostic or {}),
                            "citation_validation_reason": reason,
                            "retrieved_chunk_ids": [item.chunk_id for item in contexts],
                            "returned_cited_chunk_ids": generated.cited_chunk_ids,
                            "unknown_cited_chunk_ids": unknown_ids,
                        },
                    )
            cited = [item for item in contexts if generated and item.chunk_id in generated.cited_chunk_ids]
            non_primary_ids = [
                item.chunk_id
                for item in cited
                if not self.financial_policy.is_primary_original(item)
            ]
            if non_primary_ids:
                raise CitationValidationError(
                    "non-primary citations are not sufficient for financial facts",
                    diagnostic={
                        **(generation_diagnostic or {}),
                        "citation_validation_reason": "non_primary_original_citation",
                        "non_primary_cited_chunk_ids": non_primary_ids,
                    },
                )
            answer = (
                self.financial_policy.format_answer(generated.answer, analysis, cited)
                if generated
                else self.financial_policy.format_insufficient(assessment, analysis)
            )
        except GenerationError as error:
            answer = self.financial_policy.format_generation_failure(analysis)
            generator_called = False
            cited = []
            generation_error = type(error).__name__
            generation_diagnostic = error.diagnostic or generation_diagnostic
        trace = {"query_type": analysis.intent, "normalization": "pension-v1", "retrieved_chunk_ids": [item.chunk_id for item in contexts], "evidence_sufficient": assessment.sufficient, "assessment_reason": assessment.reason, "generator": type(self.generator).__name__, "generator_attempted": generator_attempted, "generator_called": generator_called, "cited_chunk_ids": [item.chunk_id for item in cited], "generation_error": generation_error, "generation_diagnostic": generation_diagnostic, "financial_policy": {"recommendation_context": False, "profile_complete": False, "reasons": []}}
        if generated:
            trace.update({"generation_model": generated.model, "generation_latency_ms": round(generated.latency_ms, 3), "generation_finish_reason": generated.finish_reason, "generation_usage": generated.usage})
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": trace, "answer": answer}
