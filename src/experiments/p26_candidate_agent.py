"""P26 전용 candidate Agent.

운영 ``PensionAgent``는 변경하지 않는다. 이 경로는 P24-B의 requirement
retrieval/matcher와 P25의 provenance·금융 답변 정책을 함께 평가하기 위한
shadow composition이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.experiments.conditional_shadow_agent import ConditionalRoutingShadowAgent
from src.generation.errors import CitationValidationError, GenerationError
from src.orchestration.evidence_assessor import EvidenceAssessment
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy


@dataclass
class P26CandidateAgent(ConditionalRoutingShadowAgent):
    """P24-B candidate preparation에 원본 provenance·금융 표현 정책을 적용한다."""

    financial_policy: FinancialAnswerPolicy = field(default_factory=FinancialAnswerPolicy)

    def answer(self, question: str, top_k: int = 5) -> dict:
        analysis = self.analyzer.analyze(question)
        support = self.router.support_classifier.classify(analysis.question)
        # 개인계좌·미래 외부정보·prompt injection은 추천/clarify 흐름으로
        # 흡수하지 않는다. 이 세 범주는 검색·HCX 전에 명시적인 safe block을
        # 반환해야 단일턴 계약을 만족한다.
        if not support.supported and (
            support.category in {
                "personal_account_lookup",
                "unavailable_external_information",
                "prompt_injection",
            }
            or support.reason == "external_prediction_requested"
        ):
            policy_category = (
                "unavailable_external_information"
                if support.reason == "external_prediction_requested"
                else support.category
            )
            return self._policy_response(
                analysis,
                self.financial_policy.format_unsupported_safety_block(policy_category),
                policy_category,
                (support.reason,),
            )
        recommendation = self.financial_policy.recommendation_decision(analysis)
        if recommendation.is_recommendation_context:
            answer = (
                self.financial_policy.format_recommendation_comparison_guidance(recommendation)
                if recommendation.profile_complete
                else self.financial_policy.format_recommendation_clarification(recommendation)
            )
            reason = "recommendation_comparison_only" if recommendation.profile_complete else "conditional_recommendation_requires_user_conditions"
            return self._policy_response(analysis, answer, reason, recommendation.reasons)
        if self.financial_policy.requires_personal_tax_clarification(analysis):
            return self._policy_response(
                analysis,
                self.financial_policy.format_personal_tax_clarification(),
                "personal_tax_conditions_required",
                ("personal_tax_optimization",),
            )

        plan = self.prepare(question, top_k)
        analysis = plan.analysis
        contexts = list(plan.contexts)
        assessment = plan.assessment
        if assessment.sufficient and not any(
            self.financial_policy.is_primary_original(context) for context in contexts
        ):
            assessment = EvidenceAssessment(False, "primary_original_evidence_missing")

        generator_attempted = assessment.sufficient
        generator_called = generator_attempted
        generated = None
        generation_error = None
        generation_diagnostic = None
        cited = []
        try:
            if generator_called:
                active_generator = self._compound_generator(plan.selection) if plan.selection is not None else self.generator
                generated = active_generator.generate(
                    question=analysis.question,
                    contexts=contexts,
                    query_analysis=analysis,
                )
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
                cited = [item for item in contexts if item.chunk_id in generated.cited_chunk_ids]
                non_primary_ids = [
                    item.chunk_id for item in cited if not self.financial_policy.is_primary_original(item)
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
                answer = self.financial_policy.format_answer(generated.answer, analysis, cited)
            else:
                answer = self.financial_policy.format_insufficient(assessment, analysis)
        except GenerationError as error:
            answer = self.financial_policy.format_generation_failure(analysis)
            generator_called = False
            cited = []
            generation_error = type(error).__name__
            generation_diagnostic = error.diagnostic or generation_diagnostic

        trace = {
            "query_type": analysis.intent,
            "normalization": "pension-v1",
            "route": plan.route.route,
            "route_reasons": plan.route.reasons,
            "retrieved_chunk_ids": [item.chunk_id for item in contexts],
            "selected_requirement_slots": [slot.name for slot in plan.requirement_case.slots]
            if plan.requirement_case
            else [],
            "missing_requirement_slots": assessment.missing_requirements,
            "evidence_sufficient": assessment.sufficient,
            "assessment_reason": assessment.reason,
            "generator": type(self.generator).__name__,
            "generator_attempted": generator_attempted,
            "generator_called": generator_called,
            "cited_chunk_ids": [item.chunk_id for item in cited],
            "generation_error": generation_error,
            "generation_diagnostic": generation_diagnostic,
        }
        trace.update(self._preparation_trace(plan))
        if generated:
            trace.update(
                {
                    "generation_model": generated.model,
                    "generation_latency_ms": round(generated.latency_ms, 3),
                    "generation_finish_reason": generated.finish_reason,
                    "generation_usage": generated.usage,
                }
            )
        return {
            "question": analysis.question,
            "retrieved_context": contexts,
            "think_trace": trace,
            "answer": answer,
        }

    @staticmethod
    def _policy_response(analysis, answer: str, reason: str, reasons) -> dict:
        """단일턴 정책 응답은 HCX·citation 없이도 필요한 확인 항목을 완결한다."""
        return {
            "question": analysis.question,
            "retrieved_context": [],
            "think_trace": {
                "query_type": analysis.intent,
                "normalization": "pension-v1",
                "route": "policy",
                "route_reasons": list(reasons),
                "retrieved_chunk_ids": [],
                "selected_requirement_slots": [],
                "missing_requirement_slots": [],
                "evidence_sufficient": False,
                "assessment_reason": reason,
                "generator": "policy",
                "generator_attempted": False,
                "generator_called": False,
                "cited_chunk_ids": [],
                "generation_error": None,
                "generation_diagnostic": None,
            },
            "answer": answer,
        }
