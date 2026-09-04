"""Isolated P45 single-subject Closed factual E2E composition.

This is intentionally separate from the browser/candidate Agent.  It connects
the frozen P42 resolver-first selector and P43 retrieval handoff only for the
P45 evaluation lane; genuine comparisons remain unresolved by contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.experiments.direct_requirement_selector import DIRECT_REQUIREMENT_LABELS
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.experiments.query_understanding import SupportClassifier
from src.generation.bounded_evidence_prompt_builder import BoundedEvidencePromptBuilder
from src.generation.claim_stance import ClaimStance, resolve_claim_stance
from src.generation.errors import CitationValidationError, GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.generation.versioned_generator_prompt import VersionedGeneratorPrompt, load_generator_prompt
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.required_fact_completeness import RequiredFactCompletenessGate
from src.orchestration.query_analyzer import QueryAnalyzer


class DirectRequirementCitationPromptBuilder(NativeStructuredOutputPromptBuilder):
    """Native SO answer contract bound to direct-selector requirements/evidence."""

    def __init__(
        self,
        requirements: tuple[str, ...],
        stance: ClaimStance = ClaimStance(),
        prompt_contract: VersionedGeneratorPrompt | None = None,
    ):
        self.requirements = requirements
        self.stance = stance
        self.prompt_contract = prompt_contract or load_generator_prompt()

    def build(self, question, contexts):
        allowed = ", ".join(context.chunk_id for context in contexts)
        requested = "\n".join(
            f"- {key}: {DIRECT_REQUIREMENT_LABELS[key]}" for key in self.requirements
        )
        evidence = "\n\n".join(
            f"[EVIDENCE]\ncitation_id: {context.chunk_id}\ncontent: {context.text}"
            for context in contexts
        )
        return (
            f"{self.prompt_contract.runtime_instruction()}\n\n"
            "질문 요구 항목이 여러 개면 각 항목을 빠뜨리지 말고 구분해 설명하세요. 특히 연간 총보수율과 "
            "기간별 비용 예시, 현재 위험등급과 과거 변경 이력을 서로 바꾸지 마세요.\n\n"
            f"[Required factual units]\n{requested}\n\n[Question]\n{question}\n\n"
            f"{evidence}\n\n[Allowed citation_id]\n{allowed}\n\n"
            f"[Final style checklist]\n{self.prompt_contract.runtime_checklist()}"
            f"{self.stance.writer_instruction()}"
        )

    def payload(self, question, contexts, model):
        payload = super().payload(question, contexts, model)
        payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["items"] = {
            "type": "string", "enum": [context.chunk_id for context in contexts],
        }
        return payload


class RequiredFactRepairPromptBuilder(NativeStructuredOutputPromptBuilder):
    """One bounded repair request using the same selected evidence only."""

    def __init__(self, required_facts: tuple[object, ...], prompt_contract: VersionedGeneratorPrompt | None = None):
        self.required_facts = required_facts
        self.prompt_contract = prompt_contract or load_generator_prompt()

    def build(self, question, contexts):
        allowed = ", ".join(context.chunk_id for context in contexts)
        evidence = "\n\n".join(
            f"[EVIDENCE]\ncitation_id: {context.chunk_id}\ncontent: {context.text}"
            for context in contexts
        )
        required = "\n".join(f"- {fact.prompt_text}" for fact in self.required_facts)
        return (
            f"{self.prompt_contract.runtime_instruction()}\n\n"
            "아래는 같은 질문과 이미 선택된 원본 evidence입니다. 이전 답변이 선택 근거 안의 필수 사실을 "
            "누락해 한 번만 보완합니다. 아래 [필수 사실]을 모두 답하되, evidence 밖 사실·수치·조건은 "
            "추가하지 마세요. 질문하지 않은 인접 field도 추가하지 마세요. JSON 객체만 반환하세요: "
            '{"answer": string, "cited_chunk_ids": [string]}. cited_chunk_ids에는 실제 사용한 아래 허용 '
            "citation_id를 하나 이상 원문 그대로 넣으세요.\n\n"
            f"[필수 사실]\n{required}\n\n[질문]\n{question}\n\n{evidence}\n\n[허용 citation_id]\n{allowed}\n\n"
            f"[Final style checklist]\n{self.prompt_contract.runtime_checklist()}"
        )


@dataclass
class DirectRequirementE2EAgent:
    """Fail-closed single-subject P45 path with strict citation validation."""

    scoped_selector: object
    preparation: ScopedFrontendPreparationShadow
    generator: object
    analyzer: QueryAnalyzer = QueryAnalyzer()
    financial_policy: FinancialAnswerPolicy = FinancialAnswerPolicy()
    support_classifier: SupportClassifier = field(default_factory=SupportClassifier)
    required_fact_gate: RequiredFactCompletenessGate = field(default_factory=RequiredFactCompletenessGate)
    prompt_contract: VersionedGeneratorPrompt = field(default_factory=load_generator_prompt)

    def __post_init__(self) -> None:
        self.prompt_contract.assert_runtime_ready()

    def _answer_generator(self, requirements: tuple[str, ...], stance: ClaimStance):
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=DirectRequirementCitationPromptBuilder(requirements, stance, self.prompt_contract),
            rate_limiter=self.generator.rate_limiter,
            sleeper=self.generator.sleeper,
            response_capture=self.generator.response_capture,
        )

    def _bounded_generator(
        self,
        supported_requirements: tuple[str, ...],
        unsupported_requirements: tuple[str, ...],
    ):
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=BoundedEvidencePromptBuilder(
                supported_requirements=(DIRECT_REQUIREMENT_LABELS[item] for item in supported_requirements),
                unsupported_requirements=(DIRECT_REQUIREMENT_LABELS[item] for item in unsupported_requirements),
                prompt_contract=self.prompt_contract,
            ),
            rate_limiter=self.generator.rate_limiter,
            sleeper=self.generator.sleeper,
            response_capture=self.generator.response_capture,
        )

    def _completeness_repair_generator(self, requirements: tuple[str, ...]):
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        facts = self.required_fact_gate.facts_for(requirements)
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=RequiredFactRepairPromptBuilder(facts, self.prompt_contract),
            rate_limiter=self.generator.rate_limiter,
            sleeper=self.generator.sleeper,
            response_capture=self.generator.response_capture,
        )

    @staticmethod
    def _frontend_payload(selected) -> dict:
        selection = selected.selection
        return {
            "status": selected.status,
            "active_subject": selected.active_subject,
            "selected_requirements": list(selection.selected_requirements) if selection else [],
            "allowed_requirements": list(selected.allowed_requirements),
        }

    def _insufficient(self, question, trace, reason):
        trace.update({
            "evidence_sufficient": False,
            "evidence_status": "none",
            # A clear factual question with no usable document evidence is a
            # bounded answer, not a request for user conditions.  The wording
            # below explicitly preserves that evidence limit.
            "outcome": "bounded_answer",
            "assessment_reason": reason,
            "generator_attempted": False,
            "generator_called": False,
            "cited_chunk_ids": [],
            "cited_documents": [],
            "generation_error": None,
        })
        return {
            "question": question,
            "retrieved_context": [],
            "think_trace": trace,
            "answer": "[답변]\n제공된 원본 문서에서 질문의 핵심 정보를 직접 확인하지 못했습니다. 근거가 없는 내용은 추측하지 않겠습니다.\n\n[유의사항]\n- 관련 있어 보이는 일반 안내문을 질문의 직접 근거로 대신 사용하지 않습니다.",
        }

    def _policy_response(self, analysis: QueryAnalysis, answer: str, *, outcome: str, reason: str, reasons: tuple[str, ...] = ()) -> dict:
        """Return a host-owned safe/clarification response before HCX calls.

        This attaches the existing P49 policy contract to the scoped runtime;
        it does not alter selector, retrieval, evidence, or generation rules.
        Clarification has no fabricated citation because no factual evidence is
        being asserted.
        """
        return {
            "question": analysis.question,
            "retrieved_context": [],
            "think_trace": {
                "query_type": analysis.intent,
                "normalization": "pension-v1",
                "route": "policy",
                "route_reasons": list(reasons),
                "outcome": outcome,
                "retrieved_chunk_ids": [],
                "selected_evidence_chunk_ids": [],
                "selected_evidence_ids": [],
                "cited_chunk_ids": [],
                "cited_documents": [],
                "evidence_sufficient": False,
                "evidence_status": "none",
                "assessment_reason": reason,
                "generator_attempted": False,
                "generator_called": False,
                "generation_error": None,
                "generation_diagnostic": None,
                "generator_model": getattr(getattr(self.generator, "config", None), "hcx_model", None),
                **self.prompt_contract.trace_fields(),
            },
            "answer": answer,
        }

    def answer(self, question: str, top_k: int = 5) -> dict:
        """Answer through the frozen scoped path.

        ``top_k`` is accepted to preserve the public API contract.  It is not
        allowed to reopen raw BM25 retrieval: this path has a frozen,
        requirement-scoped context budget in ``ScopedFrontendPreparationShadow``.
        """
        analysis = self.analyzer.analyze(question)
        support = self.support_classifier.classify(analysis.question)
        # These established safety policies must not invoke the selector or
        # answer model. Recommendation requests are deliberately handled by
        # the clarification policy below rather than this safe-block branch.
        if not support.supported and support.category in {
            "prompt_injection", "personal_account_lookup",
        }:
            return self._policy_response(
                analysis,
                self.financial_policy.format_unsupported_safety_block(support.category),
                outcome="safe_block",
                reason=support.category,
                reasons=(support.reason,),
            )
        # A concrete future value is an evidence-limit question, not a
        # suitability/recommendation request merely because it contains a
        # risk-related word or horizon.  Bound it before profile handling.
        if self.financial_policy.requires_future_value_boundary(analysis):
            return self._policy_response(
                analysis,
                self.financial_policy.format_future_value_boundary(),
                outcome="bounded_answer",
                reason="future_value_not_supported_by_current_evidence",
            )
        if not support.supported and support.category == "unavailable_external_information":
            return self._policy_response(
                analysis,
                self.financial_policy.format_unsupported_safety_block(support.category),
                outcome="safe_block",
                reason=support.category,
                reasons=(support.reason,),
            )
        recommendation = self.financial_policy.recommendation_decision(analysis)
        if recommendation.is_recommendation_context and not recommendation.profile_complete:
            return self._policy_response(
                analysis,
                self.financial_policy.format_recommendation_clarification(recommendation),
                outcome="clarification_required",
                reason="conditional_recommendation_requires_user_conditions",
                reasons=recommendation.reasons,
            )
        if self.financial_policy.requires_personal_tax_clarification(analysis):
            return self._policy_response(
                analysis,
                self.financial_policy.format_personal_tax_clarification(),
                outcome="clarification_required",
                reason="personal_tax_conditions_required",
            )
        if self.financial_policy.product_reference_decision(analysis).requires_product_identification:
            return self._policy_response(
                analysis,
                self.financial_policy.format_product_reference_clarification(),
                outcome="clarification_required",
                reason="product_identification_required",
            )
        selected = self.scoped_selector.select(analysis.question)
        selection = selected.selection
        trace = {
            "route": "p45_single_subject_direct_requirement",
            "active_subject": selected.active_subject,
            "frontend_status": selected.status,
            "frontend_reason": selected.reason,
            "selector_unresolved": selection.unresolved if selection else None,
            "selector_diagnostic": selection.diagnostic if selection else None,
            "selected_requirements": list(selection.selected_requirements) if selection else [],
            "allowed_requirements": list(selected.allowed_requirements),
            "resolution": selected.resolution.as_dict(),
            "binding": selected.binding.as_dict() if selected.binding else None,
            "requested_top_k": top_k,
            "generator_model": getattr(getattr(self.generator, "config", None), "hcx_model", None),
            **self.prompt_contract.trace_fields(),
        }
        if (
            selected.status != "selected" or selection is None or selection.unresolved
            or not selection.schema_valid or not selection.ontology_valid
            or selected.binding is None or selected.binding.scope_conflicts
            or selected.binding.unresolved_references or selected.binding.incomplete_reasons
        ):
            return self._insufficient(analysis.question, trace, "single_subject_frontend_unresolved")

        stance = resolve_claim_stance(analysis.question, tuple(selection.selected_requirements))
        trace.update({
            "claim_stance": stance.as_dict(),
            "query_modality": stance.query_modality,
            "normalized_claim": stance.normalized_claim,
            "claim_polarity": stance.claim_polarity,
            "stance_reason": stance.stance_reason,
        })

        prepared = self.preparation.prepare(analysis.question, self._frontend_payload(selected))
        trace.update({
            "preparation_status": prepared.status,
            "retrieval_queries": {
                requirement: self.preparation.retrieval_query(selected.active_subject, requirement)
                for requirement in selection.selected_requirements
            },
            "requirement_candidate_ids": {key: list(value) for key, value in prepared.requirement_candidates.items()},
            "retrieved_chunk_ids": [context.chunk_id for context in prepared.contexts],
            "selected_evidence_chunk_ids": [context.chunk_id for context in prepared.contexts],
            "selected_evidence_ids": [context.chunk_id for context in prepared.contexts],
        })
        missing = [requirement for requirement in selection.selected_requirements if not prepared.requirement_candidates.get(requirement)]
        supported = [requirement for requirement in selection.selected_requirements if requirement not in missing]
        contexts = list(prepared.contexts)
        if prepared.status != "prepared" or not contexts:
            trace["missing_requirements"] = missing
            return self._insufficient(analysis.question, trace, "direct_requirement_evidence_insufficient")
        non_primary = [context.chunk_id for context in contexts if not self.financial_policy.is_primary_original(context)]
        if non_primary:
            trace["non_primary_context_ids"] = non_primary
            return self._insufficient(analysis.question, trace, "primary_original_evidence_missing")

        evidence_status = "full" if not missing else "partial"
        trace["supported_requirements"] = supported
        trace["missing_requirements"] = missing
        trace["evidence_sufficient"] = not missing
        trace["evidence_status"] = evidence_status
        trace["outcome"] = "supported_answer" if not missing else "bounded_answer"
        trace["assessment_reason"] = (
            "direct_requirement_evidence_sufficient"
            if not missing
            else "direct_requirement_evidence_partial"
        )
        trace["generator_attempted"] = True
        generated = None
        cited = []
        host_completion_citation_ids: tuple[str, ...] = ()
        try:
            active_generator = (
                self._answer_generator(tuple(selection.selected_requirements), stance)
                if not missing
                else self._bounded_generator(tuple(supported), tuple(missing))
            )
            generated = active_generator.generate(
                question=analysis.question, contexts=contexts, query_analysis=analysis,
            )
            if not missing:
                generated_answer = stance.apply_answer_prefix(generated.answer)
            else:
                generated_answer = generated.answer
            completeness = self.required_fact_gate.assess(
                tuple(selection.selected_requirements), contexts, generated.answer,
            )
            trace["required_fact_completeness_initial"] = {
                "applicable": completeness.applicable,
                "required_fact_keys": list(completeness.required_fact_keys),
                "missing_fact_keys": list(completeness.missing_fact_keys),
                "evidence_contract_valid": completeness.evidence_contract_valid,
            }
            if completeness.applicable and not completeness.evidence_contract_valid:
                raise CitationValidationError(
                    "required-fact contract is not present in selected evidence",
                    diagnostic={"citation_validation_reason": "required_fact_contract_evidence_missing"},
                )
            if completeness.missing_fact_keys:
                repaired = self._completeness_repair_generator(tuple(selection.selected_requirements)).generate(
                    question=analysis.question, contexts=contexts, query_analysis=analysis,
                )
                repaired_completeness = self.required_fact_gate.assess(
                    tuple(selection.selected_requirements), contexts, repaired.answer,
                )
                trace["required_fact_completeness_repair"] = {
                    "attempted": True,
                    "required_fact_keys": list(repaired_completeness.required_fact_keys),
                    "missing_fact_keys": list(repaired_completeness.missing_fact_keys),
                    "evidence_contract_valid": repaired_completeness.evidence_contract_valid,
                }
                generated = repaired
                if repaired_completeness.missing_fact_keys:
                    completion = self.required_fact_gate.complete_missing_facts(
                        tuple(selection.selected_requirements), contexts, repaired.answer,
                    )
                    trace["required_fact_completeness_host_completion"] = {
                        "attempted": True,
                        "completed_fact_keys": list(completion.completed_fact_keys),
                        "unresolved_fact_keys": list(completion.unresolved_fact_keys),
                        "supporting_chunk_ids": list(completion.supporting_chunk_ids),
                    }
                    if completion.unresolved_fact_keys or not completion.text:
                        raise CitationValidationError(
                            "one allowed required-fact repair and exact-evidence completion did not complete selected facts",
                            diagnostic={
                                "citation_validation_reason": "required_fact_omission_after_host_completion",
                                "missing_required_fact_keys": list(completion.unresolved_fact_keys),
                            },
                        )
                    generated_answer = (stance.apply_answer_prefix(repaired.answer) if not missing else repaired.answer).rstrip()
                    generated_answer = f"{generated_answer}\n\n{completion.text}"
                    host_completion_citation_ids = completion.supporting_chunk_ids
                    final_completeness = self.required_fact_gate.assess(
                        tuple(selection.selected_requirements), contexts, generated_answer,
                    )
                    trace["required_fact_completeness_final"] = {
                        "required_fact_keys": list(final_completeness.required_fact_keys),
                        "missing_fact_keys": list(final_completeness.missing_fact_keys),
                        "evidence_contract_valid": final_completeness.evidence_contract_valid,
                    }
                    if final_completeness.missing_fact_keys or not final_completeness.evidence_contract_valid:
                        raise CitationValidationError(
                            "host completion did not satisfy exact-evidence completeness contract",
                            diagnostic={
                                "citation_validation_reason": "required_fact_omission_after_host_completion",
                                "missing_required_fact_keys": list(final_completeness.missing_fact_keys),
                            },
                        )
                else:
                    trace["required_fact_completeness_host_completion"] = {"attempted": False}
                    generated_answer = stance.apply_answer_prefix(generated.answer) if not missing else generated.answer
            else:
                trace["required_fact_completeness_repair"] = {"attempted": False}
                trace["required_fact_completeness_host_completion"] = {"attempted": False}

            allowed = {context.chunk_id for context in contexts}
            final_citation_ids = tuple(dict.fromkeys((*generated.cited_chunk_ids, *host_completion_citation_ids)))
            unknown = sorted(set(final_citation_ids) - allowed)
            if not final_citation_ids or unknown:
                raise CitationValidationError(
                    "invalid citations",
                    diagnostic={
                        **(generated.diagnostic or {}),
                        "citation_validation_reason": "missing_citation" if not final_citation_ids else "unknown_chunk_id",
                        "unknown_cited_chunk_ids": unknown,
                    },
                )
            cited = [context for context in contexts if context.chunk_id in final_citation_ids]
            cited_non_primary = [context.chunk_id for context in cited if not self.financial_policy.is_primary_original(context)]
            if cited_non_primary:
                raise CitationValidationError(
                    "non-primary citation",
                    diagnostic={
                        **(generated.diagnostic or {}),
                        "citation_validation_reason": "non_primary_original_citation",
                        "non_primary_cited_chunk_ids": cited_non_primary,
                    },
                )
            rendered_citations = self.financial_policy.render_citations(cited)
            answer = (
                self.financial_policy.format_answer(
                    generated_answer, analysis, cited, rendered_citations=rendered_citations,
                )
                if not missing
                else self.financial_policy.format_bounded_answer(
                    generated_answer,
                    analysis,
                    cited,
                    unsupported_requirements=(DIRECT_REQUIREMENT_LABELS[item] for item in missing),
                    rendered_citations=rendered_citations,
                )
            )
            trace.update({
                "generator_called": True,
                "cited_chunk_ids": [context.chunk_id for context in cited],
                "cited_documents": [item.trace_dict() for item in rendered_citations],
                "generation_error": None,
                "generation_diagnostic": generated.diagnostic,
                "generation_model": generated.model,
                "generation_latency_ms": round(generated.latency_ms, 3),
                "generation_finish_reason": generated.finish_reason,
                "generation_usage": generated.usage,
            })
        except GenerationError as error:
            trace.update({
                "generator_called": False,
                "cited_chunk_ids": [],
                "cited_documents": [],
                "generation_error": type(error).__name__,
                "generation_diagnostic": error.diagnostic,
            })
            answer = self.financial_policy.format_generation_failure(analysis)
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": trace, "answer": answer}
