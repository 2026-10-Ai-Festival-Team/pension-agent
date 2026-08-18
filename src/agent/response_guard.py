from __future__ import annotations

from src.schemas.models import AnswerMode, QuestionAnalysis, RetrievalResult


INJECTION_MARKERS = ("이전 지시", "시스템 프롬프트", "문서를 무시", "근거는 필요 없", "지시를 모두 무시")
DOMAIN_MARKERS = ("연금", "irp", "db", "dc", "퇴직", "세액공제", "과세", "세금", "펀드", "투자신탁", "etf", "실물이전", "isa", "디폴트옵션", "위험등급", "채권", "국공채")


def detect_prompt_injection(question: str) -> bool:
    normalized = question.replace(" ", "")
    return any(marker.replace(" ", "") in normalized for marker in INJECTION_MARKERS)


def _in_domain(question: str) -> bool:
    lowered = question.lower()
    return any(marker in lowered for marker in DOMAIN_MARKERS)


def decide_mode(question: str, analysis: QuestionAnalysis, evidence: list[RetrievalResult]) -> AnswerMode:
    if detect_prompt_injection(question):
        return AnswerMode.ABSTAIN
    if analysis.needs_clarification:
        return AnswerMode.CLARIFY
    if not _in_domain(question) or not evidence:
        return AnswerMode.ABSTAIN
    return AnswerMode.ANSWER
