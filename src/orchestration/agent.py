from dataclasses import dataclass

from src.generation.base import AnswerGenerator
from src.orchestration.context_builder import ContextBuilder
from src.orchestration.query_analyzer import QueryAnalyzer


@dataclass
class PensionAgent:
    retriever: object
    generator: AnswerGenerator
    analyzer: QueryAnalyzer = QueryAnalyzer()
    context_builder: ContextBuilder = ContextBuilder()

    def answer(self, question: str, top_k: int = 5) -> dict:
        analysis = self.analyzer.analyze(question)
        response = self.retriever.search(analysis.question, top_k=top_k)
        contexts = self.context_builder.build(response.results)
        return {"question": analysis.question, "retrieved_context": contexts, "think_trace": {"retriever": response.tokenizer, "context_count": len(contexts)}, "answer": self.generator.generate(analysis.question, contexts)}
