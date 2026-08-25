"""Isolated P45 single-subject Closed factual E2E composition.

This is intentionally separate from the browser/candidate Agent.  It connects
the frozen P42 resolver-first selector and P43 retrieval handoff only for the
P45 evaluation lane; genuine comparisons remain unresolved by contract.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.direct_requirement_selector import DIRECT_REQUIREMENT_LABELS
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.bounded_evidence_prompt_builder import BoundedEvidencePromptBuilder
from src.generation.errors import CitationValidationError, GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.query_analyzer import QueryAnalyzer


class DirectRequirementCitationPromptBuilder(NativeStructuredOutputPromptBuilder):
    """Native SO answer contract bound to direct-selector requirements/evidence."""

    def __init__(self, requirements: tuple[str, ...]):
        self.requirements = requirements

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
            "제공된 원본 evidence만 사용해 한국어로 직접 답하세요. 답변 작성 외의 추론·추천·추측은 하지 마세요. "
            "질문 요구 항목이 여러 개면 각 항목을 빠뜨리지 말고 구분해 설명하세요. 특히 연간 총보수율과 "
            "기간별 비용 예시, 현재 위험등급과 과거 변경 이력을 서로 바꾸지 마세요. evidence에 없는 수치·조건은 "
            "만들지 마세요. JSON 객체만 반환하세요: {\"answer\": string, \"cited_chunk_ids\": [string]}. "
            "cited_chunk_ids에는 실제 사용한 아래 허용 citation_id만 원문 그대로 하나 이상 넣으세요.\n\n"
            f"[Required factual units]\n{requested}\n\n[Question]\n{question}\n\n"
            f"{evidence}\n\n[Allowed citation_id]\n{allowed}"
        )

    def payload(self, question, contexts, model):
        payload = super().payload(question, contexts, model)
        payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["items"] = {
            "type": "string", "enum": [context.chunk_id for context in contexts],
        }
        return payload


@dataclass
class DirectRequirementE2EAgent:
    """Fail-closed single-subject P45 path with strict citation validation."""

    scoped_selector: object
    preparation: ScopedFrontendPreparationShadow
    generator: object
    analyzer: QueryAnalyzer = QueryAnalyzer()
    financial_policy: FinancialAnswerPolicy = FinancialAnswerPolicy()

    def _answer_generator(self, requirements: tuple[str, ...]):
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=DirectRequirementCitationPromptBuilder(requirements),
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
            ),
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
            "outcome": "no_evidence_boundary",
            "assessment_reason": reason,
            "generator_attempted": False,
            "generator_called": False,
            "cited_chunk_ids": [],
            "generation_error": None,
        })
        return {
            "question": question,
            "retrieved_context": [],
            "think_trace": trace,
            "answer": "[답변]\n제공된 원본 문서에서 질문의 핵심 정보를 직접 확인하지 못했습니다. 근거가 없는 내용은 추측하지 않겠습니다.\n\n[유의사항]\n- 관련 있어 보이는 일반 안내문을 질문의 직접 근거로 대신 사용하지 않습니다.",
        }

    def answer(self, question: str) -> dict:
        analysis = self.analyzer.analyze(question)
        selected = self.scoped_selector.select(analysis.question)
        selection = selected.selection
        trace = {
            "route": "p45_single_subject_direct_requirement",
            "active_subject": selected.active_subject,
            "frontend_status": selected.status,
            "frontend_reason": selected.reason,
            "selected_requirements": list(selection.selected_requirements) if selection else [],
            "allowed_requirements": list(selected.allowed_requirements),
            "resolution": selected.resolution.as_dict(),
            "binding": selected.binding.as_dict() if selected.binding else None,
        }
        if (
            selected.status != "selected" or selection is None or selection.unresolved
            or not selection.schema_valid or not selection.ontology_valid
            or selected.binding is None or selected.binding.scope_conflicts
            or selected.binding.unresolved_references or selected.binding.incomplete_reasons
        ):
            return self._insufficient(analysis.question, trace, "single_subject_frontend_unresolved")

        prepared = self.preparation.prepare(analysis.question, self._frontend_payload(selected))
        trace.update({
            "preparation_status": prepared.status,
            "requirement_candidate_ids": {key: list(value) for key, value in prepared.requirement_candidates.items()},
            "retrieved_chunk_ids": [context.chunk_id for context in prepared.contexts],
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
        try:
            active_generator = (
                self._answer_generator(tuple(selection.selected_requirements))
                if not missing
                else self._bounded_generator(tuple(supported), tuple(missing))
            )
            generated = active_generator.generate(
                question=analysis.question, contexts=contexts, query_analysis=analysis,
            )
            allowed = {context.chunk_id for context in contexts}
            unknown = sorted(set(generated.cited_chunk_ids) - allowed)
            if not generated.cited_chunk_ids or unknown:
                raise CitationValidationError(
                    "invalid citations",
                    diagnostic={
                        **(generated.diagnostic or {}),
                        "citation_validation_reason": "missing_citation" if not generated.cited_chunk_ids else "unknown_chunk_id",
                        "unknown_cited_chunk_ids": unknown,
                    },
                )
            cited = [context for context in contexts if context.chunk_id in generated.cited_chunk_ids]
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
            answer = (
                self.financial_policy.format_answer(generated.answer, analysis, cited)
                if not missing
                else self.financial_policy.format_bounded_answer(
                    generated.answer,
                    analysis,
                    cited,
                    unsupported_requirements=(DIRECT_REQUIREMENT_LABELS[item] for item in missing),
                )
            )
            trace.update({
                "generator_called": True,
                "cited_chunk_ids": [context.chunk_id for context in cited],
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
                "generation_error": type(error).__name__,
                "generation_diagnostic": error.diagnostic,
            })
            answer = self.financial_policy.format_generation_failure(analysis)
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": trace, "answer": answer}
