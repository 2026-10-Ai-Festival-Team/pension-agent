from dataclasses import dataclass


@dataclass(frozen=True)
class QueryAnalysis:
    question: str


class QueryAnalyzer:
    def analyze(self, question: str) -> QueryAnalysis:
        if not question.strip():
            raise ValueError("question must not be empty")
        return QueryAnalysis(question=question.strip())
