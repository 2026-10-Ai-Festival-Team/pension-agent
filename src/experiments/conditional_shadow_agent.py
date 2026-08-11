"""P16 평가 전용 conditional-routing Shadow Agent.

운영 ``PensionAgent``를 변경하지 않는다. Simple 질문은 기존 context·generator
경로를 유지하고, compound 질문에만 requirement candidate expansion, completeness
gate, minimal citation representation을 적용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.experiments.citation_diagnosis import CitationDiagnosisPromptBuilder
from src.experiments.requirement_retrieval import expand_requirement_candidates
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.generation.errors import CitationValidationError, GenerationError
from src.generation.hcx import HyperClovaXGenerator
from src.orchestration.context_builder import ContextBuilder
from src.orchestration.evidence_assessor import EvidenceAssessment
from src.orchestration.query_analyzer import QueryAnalyzer


@dataclass
class ConditionalRoutingShadowAgent:
    retriever: object
    generator: object
    analyzer: QueryAnalyzer = field(default_factory=QueryAnalyzer)
    context_builder: ContextBuilder = field(default_factory=ContextBuilder)
    router: ExperimentalRouter = field(default_factory=ExperimentalRouter)
    gate: ExperimentalRouteGate = field(default_factory=ExperimentalRouteGate)
    requirement_retrieval_top_k: int = 5

    def _compound_generator(self, selection):
        """같은 HCX transport·limiter를 공유하되 prompt representation만 교체한다."""
        if not isinstance(self.generator, HyperClovaXGenerator):
            return self.generator
        return HyperClovaXGenerator(
            config=self.generator.config,
            transport=self.generator.transport,
            prompt_builder=CitationDiagnosisPromptBuilder(
                "B_minimal_no_other_identifier", selection
            ),
            rate_limiter=self.generator.rate_limiter,
            sleeper=self.generator.sleeper,
        )

    @staticmethod
    def _citation(result) -> str:
        page = result.locator.page_start or result.locator.sheet or "위치 정보 없음"
        return f"[출처: {result.source_path}, {page}페이지, {result.chunk_id}]"

    @staticmethod
    def _insufficient_answer(assessment: EvidenceAssessment) -> str:
        if assessment.reason == "conditional_recommendation_requires_user_conditions":
            return "추천을 위해 " + ", ".join(assessment.missing_requirements) + "을 알려주세요."
        if assessment.reason == "unsupported_or_personal_or_conditional":
            return "제공된 문서 범위 또는 개인 조건만으로는 이 요청에 답할 수 없습니다."
        return "제공된 문서에서 질문에 답할 충분한 근거를 확인하지 못했습니다."

    def answer(self, question: str, top_k: int = 5) -> dict:
        analysis = self.analyzer.analyze(question)
        route = self.router.classify(analysis)
        base_results = self.retriever.search(analysis.question, top_k=top_k).results
        requirement_case = route.requirement_case
        candidate_results = expand_requirement_candidates(
            requirement_case if route.route == "compound" else None,
            base_results,
            self.retriever,
            top_k=self.requirement_retrieval_top_k,
        )
        decision = self.gate.assess(route.route, analysis, candidate_results, requirement_case)

        selection = None
        if route.route == "compound" and requirement_case is not None:
            selection = self.gate.selector.select(requirement_case, candidate_results)
            contexts = list(selection.contexts)
        else:
            contexts = self.context_builder.build(base_results, top_k)
        assessment = EvidenceAssessment(
            decision.sufficient,
            decision.reason,
            decision.missing_slots,
            decision.selected_chunk_ids,
        )
        generator_attempted = assessment.sufficient
        generator_called = generator_attempted
        generated = None
        generation_error = None
        generation_diagnostic = None
        cited = []
        try:
            if generator_called:
                active_generator = self._compound_generator(selection) if selection is not None else self.generator
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
            answer = generated.answer if generated else self._insufficient_answer(assessment)
            if generated:
                cited = [item for item in contexts if item.chunk_id in generated.cited_chunk_ids]
                answer += "\n\n" + "\n".join(self._citation(item) for item in cited)
        except GenerationError as error:
            answer = "생성 응답을 검증하지 못했습니다. 제공된 근거를 다시 확인해 주세요."
            generator_called = False
            generation_error = type(error).__name__
            generation_diagnostic = error.diagnostic or generation_diagnostic

        trace = {
            "query_type": analysis.intent,
            "normalization": "pension-v1",
            "route": route.route,
            "route_reasons": route.reasons,
            "retrieved_chunk_ids": [item.chunk_id for item in contexts],
            "candidate_chunk_ids": [item.chunk_id for item in candidate_results],
            "selected_requirement_slots": [slot.name for slot in requirement_case.slots] if requirement_case else [],
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
        if generated:
            trace.update(
                {
                    "generation_model": generated.model,
                    "generation_latency_ms": round(generated.latency_ms, 3),
                    "generation_finish_reason": generated.finish_reason,
                    "generation_usage": generated.usage,
                }
            )
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": trace, "answer": answer}
