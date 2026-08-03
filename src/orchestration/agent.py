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
        generator_called = assessment.sufficient
        try:
            generated = self.generator.generate(question=analysis.question, contexts=contexts, query_analysis=analysis) if generator_called else None
            if generated and (not generated.cited_chunk_ids or set(generated.cited_chunk_ids)-{item.chunk_id for item in contexts}): raise CitationValidationError("invalid citations")
            answer = generated.answer if generated else self._insufficient_answer(assessment)
            cited = [item for item in contexts if generated and item.chunk_id in generated.cited_chunk_ids]
            if generated: answer += "\n\n" + "\n".join(self._citation(item) for item in cited)
        except GenerationError:
            answer = "생성 응답을 검증하지 못했습니다. 제공된 근거를 다시 확인해 주세요."; generator_called=False; cited=[]
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": {"query_type": analysis.intent, "normalization": "pension-v1", "retrieved_chunk_ids": [item.chunk_id for item in contexts], "evidence_sufficient": assessment.sufficient, "assessment_reason": assessment.reason, "generator": type(self.generator).__name__, "generator_called": generator_called}, "answer": answer}

    @staticmethod
    def _citation(item) -> str:
        page = f"{item.locator.page_start}페이지" if item.locator.page_start else "위치 정보 없음"
        return f"[출처: {item.source_path}, {page}, {item.chunk_id}]"

    @staticmethod
    def _insufficient_answer(assessment) -> str:
        if assessment.reason == "conditional_recommendation_requires_user_conditions":
            return "추천을 위해 " + ", ".join(assessment.missing_requirements) + "을 알려주세요."
        return "제공된 문서에서 질문에 답할 충분한 근거를 확인하지 못했습니다."
