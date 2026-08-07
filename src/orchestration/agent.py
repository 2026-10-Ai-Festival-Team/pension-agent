from dataclasses import dataclass

from src.generation.base import AnswerGenerator
from src.orchestration.context_builder import ContextBuilder
from src.orchestration.query_analyzer import QueryAnalyzer
from src.orchestration.evidence_assessor import EvidenceAssessor
from src.generation.errors import CitationValidationError, GenerationError


@dataclass
class PensionAgent:
    retriever: object
    generator: AnswerGenerator
    analyzer: QueryAnalyzer = QueryAnalyzer()
    context_builder: ContextBuilder = ContextBuilder()
    assessor: EvidenceAssessor = EvidenceAssessor()

    def answer(self, question: str, top_k: int = 5) -> dict:
        analysis = self.analyzer.analyze(question)
        response = self.retriever.search(analysis.question, top_k=top_k)
        contexts = self.context_builder.build(response.results, top_k)
        assessment = self.assessor.assess(analysis, contexts)
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
            answer = generated.answer if generated else self._insufficient_answer(assessment)
            cited = [item for item in contexts if generated and item.chunk_id in generated.cited_chunk_ids]
            if generated: answer += "\n\n" + "\n".join(self._citation(item) for item in cited)
        except GenerationError as error:
            answer = "생성 응답을 검증하지 못했습니다. 제공된 근거를 다시 확인해 주세요."; generator_called=False; cited=[]; generation_error=type(error).__name__; generation_diagnostic=error.diagnostic or generation_diagnostic
        trace = {"query_type": analysis.intent, "normalization": "pension-v1", "retrieved_chunk_ids": [item.chunk_id for item in contexts], "evidence_sufficient": assessment.sufficient, "assessment_reason": assessment.reason, "generator": type(self.generator).__name__, "generator_attempted": generator_attempted, "generator_called": generator_called, "cited_chunk_ids": [item.chunk_id for item in cited], "generation_error": generation_error, "generation_diagnostic": generation_diagnostic}
        if generated:
            trace.update({"generation_model": generated.model, "generation_latency_ms": round(generated.latency_ms, 3), "generation_finish_reason": generated.finish_reason, "generation_usage": generated.usage})
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": trace, "answer": answer}

    @staticmethod
    def _citation(item) -> str:
        page = f"{item.locator.page_start}페이지" if item.locator.page_start else "위치 정보 없음"
        return f"[출처: {item.source_path}, {page}, {item.chunk_id}]"

    @staticmethod
    def _insufficient_answer(assessment) -> str:
        if assessment.reason == "conditional_recommendation_requires_user_conditions":
            return "추천을 위해 " + ", ".join(assessment.missing_requirements) + "을 알려주세요."
        return "제공된 문서에서 질문에 답할 충분한 근거를 확인하지 못했습니다."
