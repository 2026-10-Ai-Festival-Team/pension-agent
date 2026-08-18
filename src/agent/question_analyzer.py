from __future__ import annotations

import json
import re

from src.agent.prompts import ANALYZER_SYSTEM_PROMPT
from src.llm.hyperclova import HyperClovaClient, HyperClovaError
from src.schemas.models import QuestionAnalysis


def _json_object(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("JSON 객체가 없습니다.")
    return json.loads(match.group())


RECOMMENDATION_MARKERS = ("추천", "골라", "선택해", "가장 좋은")
ACCOUNT_MARKERS = ("IRP", "연금저축", "DC", "DB")
HORIZON_MARKERS = ("년", "개월", "장기", "단기", "은퇴")
RISK_MARKERS = ("위험", "손실", "안정", "변동성", "공격", "보수적")


def _apply_clarification_policy(question: str, analysis: QuestionAnalysis) -> QuestionAnalysis:
    """Use deterministic checks so factual questions are not needlessly clarified."""
    is_recommendation = any(marker in question for marker in RECOMMENDATION_MARKERS)
    if not is_recommendation:
        analysis.needs_clarification = False
        analysis.missing_information = []
        return analysis

    analysis.intent = "recommendation"
    # A request to compare named candidates is answerable from their documents.
    if "비교" in question:
        analysis.needs_clarification = False
        analysis.missing_information = []
        return analysis

    missing = []
    if not any(marker.lower() in question.lower() for marker in ACCOUNT_MARKERS):
        missing.append("계좌 유형")
    if not any(marker in question for marker in HORIZON_MARKERS):
        missing.append("투자 기간")
    if not any(marker in question for marker in RISK_MARKERS):
        missing.append("위험 감내 수준")
    if "목적" not in question:
        missing.append("투자 목적")
    analysis.needs_clarification = bool(missing)
    analysis.missing_information = missing
    return analysis


class QuestionAnalyzer:
    def __init__(self, client: HyperClovaClient | None):
        self.client = client

    def _fallback(self, question: str) -> QuestionAnalysis:
        recommendation = any(term in question for term in RECOMMENDATION_MARKERS)
        analysis = QuestionAnalysis(
            intent="recommendation" if recommendation else "other",
            search_queries=[question],
        )
        return _apply_clarification_policy(question, analysis)

    def analyze(self, question: str) -> QuestionAnalysis:
        if not self.client or not self.client.configured:
            return self._fallback(question)
        try:
            response = self.client.chat(ANALYZER_SYSTEM_PROMPT, question, max_tokens=512, temperature=0.0)
            parsed = QuestionAnalysis.model_validate(_json_object(response))
            parsed.search_queries = [query.strip() for query in parsed.search_queries[:3] if query.strip()] or [question]
            return _apply_clarification_policy(question, parsed)
        except (HyperClovaError, ValueError, json.JSONDecodeError):
            return self._fallback(question)
