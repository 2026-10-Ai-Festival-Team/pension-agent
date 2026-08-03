import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryAnalysis:
    question: str
    intent: str
    product_codes: list[str]
    entities: list[str]
    requires_comparison: bool
    requires_user_conditions: bool


class QueryAnalyzer:
    def analyze(self, question: str) -> QueryAnalysis:
        if not question.strip():
            raise ValueError("question must not be empty")
        normalized = question.strip()
        codes = [code.upper() for code in re.findall(r"KR[A-Z0-9]{10}", normalized, re.I)]
        entities = [item for item in ("DB", "DC", "IRP") if re.search(rf"\b{item}\b", normalized, re.I)]
        conditional = any(word in normalized for word in ("추천", "어떤 상품", "적합"))
        comparison = any(word in normalized for word in ("비교", "차이", "어느", "각각")) or len(entities) >= 2
        personal = any(word in normalized for word in ("현재 제", "내 계좌", "내 IRP", "개인 계좌"))
        intent = "unsupported_or_personal" if personal else "conditional_recommendation" if conditional else "product_explanation" if codes else "tax" if any(word in normalized for word in ("세금", "과세", "공제")) else "pension_system"
        return QueryAnalysis(normalized, intent, codes, entities, comparison, conditional)
