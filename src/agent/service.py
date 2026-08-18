from __future__ import annotations

import json

from src.agent.answer_generator import AnswerGenerator
from src.agent.question_analyzer import QuestionAnalyzer
from src.agent.response_guard import decide_mode
from src.retrieval.retriever import Retriever
from src.schemas.models import AnswerMode, PipelineResult, RetrievalResult


class PensionAgentService:
    def __init__(self, retriever: Retriever, analyzer: QuestionAnalyzer, generator: AnswerGenerator, top_k: int = 5):
        self.retriever = retriever
        self.analyzer = analyzer
        self.generator = generator
        self.top_k = top_k

    @staticmethod
    def format_context(results: list[RetrievalResult]) -> str:
        return "\n\n".join(
            f"[DOC={item.document_id} | PAGE={item.page if item.page is not None else 'N/A'}]\n{item.text}"
            for item in results
        )

    def answer(self, question_id: str, question: str) -> PipelineResult:
        analysis = self.analyzer.analyze(question)
        merged: dict[str, RetrievalResult] = {}
        for query in analysis.search_queries[:3] or [question]:
            for result in self.retriever.retrieve(query, self.top_k):
                previous = merged.get(result.chunk_id)
                if previous is None or result.score > previous.score:
                    merged[result.chunk_id] = result
        evidence = sorted(merged.values(), key=lambda item: -item.score)[: self.top_k]
        mode = decide_mode(question, analysis, evidence)
        used_evidence = evidence if mode == AnswerMode.ANSWER else []
        context = self.format_context(used_evidence)
        answer = self.generator.generate(question, context, mode, analysis)
        trace = {
            "intent": analysis.intent,
            "search_queries": analysis.search_queries,
            "used_documents": list(dict.fromkeys(item.document_id for item in used_evidence)),
            "action": mode.value.lower(),
            "checks": ["근거 문서 존재 확인", "사용 근거 출처 표시"],
        }
        return PipelineResult(question_id=question_id, question=question, retrieved_context=context, think_trace=json.dumps(trace, ensure_ascii=False), answer=answer)
