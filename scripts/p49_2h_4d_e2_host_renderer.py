"""Deterministic final-question renderer for the P49-2H-4D-E2 banmal probe.

This renderer owns wording only for the explicit E2 supported/clarification
rows. It receives immutable semantic slots and host-owned register controls,
then returns a question retaining subject, target or missing conditions, and
a validator-recognized banmal ending. It never owns evidence, outcome, answer
content, or validation policy.
"""
from __future__ import annotations

from typing import Any


RENDERER_ID = "P49-2H-4D-E2-host-banmal-surface-v1"
SUPPORTED_LANES = frozenset({"supported_answer", "clarification_required"})
FAMILIES = frozenset({"direct", "confirmation", "misconception", "planning", "evidence_check"})

CONTEXTS = {
    "이직/퇴직 직후": "퇴직 직후에",
    "이전 신청 중": "이전 신청 중에",
    "상담 전 확인": "상담 전에",
    "상품 비교 전 확인": "상품 비교 전에",
    "세액공제 계산 전": "세액공제 계산 전에",
    "서류 준비 중": "서류 준비 중에",
}

# Each phrase includes an unchanged-validator scope marker where required.
# E2 fails closed: a new requirement needs a reviewed phrase before entering
# this host-owned surface route.
SUPPORTED_TOPICS = {
    "DB.benefit_determination": "퇴직급여 계산 기준",
    "DB.operation_party": "적립금 운용 주체",
    "DC.operation_party": "적립금 운용 주체",
    "retirement_pension.ETF.direct_trade_scope": "ETF 직접 매매 범위와 레버리지·인버스 제한",
    "product.risk_grade.change_possibility": "위험등급 변경 가능 여부",
    "ISA.transfer.additional_tax_credit": "만기자금 이전 추가 세액공제",
    "retirement_income.IRP_transfer.tax_timing": "연금 수령 시 세금 처리 시점",
    "pension_savings.tax_credit.limit": "세액공제 대상 납입 한도",
}


def validate_renderer_control(control: dict[str, Any], lane: str) -> None:
    renderer = control.get("host_question_renderer")
    if not isinstance(renderer, dict):
        raise ValueError("E2 host_question_renderer is required")
    if lane not in SUPPORTED_LANES:
        raise ValueError("E2 host renderer is limited to supported/clarification lanes")
    if renderer.get("renderer_id") != RENDERER_ID:
        raise ValueError("unknown E2 host question renderer")
    if renderer.get("family") not in FAMILIES:
        raise ValueError("E2 host question renderer family is unsupported")
    if control.get("register") not in {"casual_banmal", "terse_banmal"}:
        raise ValueError("E2 host question renderer requires a banmal register")
    if control.get("context_frame") not in CONTEXTS:
        raise ValueError("E2 host question renderer context is unsupported")


def _ending(register: str, family: str) -> str:
    casual = {
        "direct": "뭐야?",
        "confirmation": "맞아?",
        "misconception": "되는 거야?",
        "planning": "어떻게 해?",
        "evidence_check": "확인할 수 있어?",
    }
    terse = {
        "direct": "뭐임?",
        "confirmation": "맞지?",
        "misconception": "됨?",
        "planning": "확인할 필요 있음?",
        "evidence_check": "확인할 수 있음?",
    }
    return (casual if register == "casual_banmal" else terse)[family]


def _supported_question(semantic: dict[str, Any], control: dict[str, Any], family: str) -> str:
    host = semantic["host_question_contract"]
    requirement = host.get("canonical_requirement")
    topic = SUPPORTED_TOPICS.get(requirement)
    if topic is None:
        raise ValueError(f"E2 host renderer has no reviewed topic for {requirement}")
    context = CONTEXTS[control["context_frame"]]
    subject = host["subject"]
    ending = _ending(control["register"], family)
    if control["register"] == "casual_banmal":
        templates = {
            "direct": f"{context} {subject}의 {topic}은 {ending}",
            "confirmation": f"{context} {subject}의 {topic}을 확인하는 거 {ending}",
            "misconception": f"{context} {subject}의 {topic}을 다른 기준으로 보면 {ending}",
            "planning": f"{context} {subject}의 {topic}을 미리 {ending}",
            "evidence_check": f"{context} {subject}의 {topic}은 자료에서 {ending}",
        }
    else:
        # The terse families intentionally use a different sentence skeleton,
        # not merely a different suffix, so register diversity cannot create
        # a deterministic near-duplicate of the casual question.
        templates = {
            "direct": f"{context} {subject} {topic} 뭐임?",
            "confirmation": f"{context} {subject} {topic}은 어떤 기준임?",
            "misconception": f"{context} {subject} {topic}을 다른 기준으로 보면 됨?",
            "planning": f"{context} {subject} {topic} 미리 확인할 필요 있음?",
            "evidence_check": f"{context} {subject} {topic}은 자료에서 확인할 수 있음?",
        }
    return templates[family]


def _clarification_question(semantic: dict[str, Any], control: dict[str, Any], family: str) -> str:
    host = semantic["host_question_contract"]
    subject = host["subject"]
    context = CONTEXTS[control["context_frame"]]
    decision = semantic["decision_target"]
    conditions = semantic["missing_conditions"]
    if not conditions:
        raise ValueError("E2 clarification renderer requires missing_conditions")
    condition_text = "와 ".join(conditions)
    ending = _ending(control["register"], family)
    if control["register"] == "casual_banmal":
        templates = {
            "direct": f"{context} {subject}에서 {decision}의 결정 여부를 보려면 {condition_text}에 따라 어떻게 달라지는지 {ending}",
            "confirmation": f"{context} {subject}의 {decision} 결정 여부는 {condition_text}에 따라 달라지는 거 {ending}",
            "misconception": f"{context} {subject}에서 {decision}의 결정 여부도 {condition_text}에 따라 달라지는데, 조건을 안 봐도 정할 수 있는 {ending}",
            "planning": f"{context} {subject}의 {decision}를 정하려면 {condition_text}에 따라 어떤 선택이 가능한지 {ending}",
            "evidence_check": f"{context} {subject}의 {decision} 결정 여부가 {condition_text}에 따라 어떻게 달라지는지 {ending}",
        }
    else:
        templates = {
            "direct": f"{context} {subject} {decision} 결정 여부는 {condition_text}에 따라 달라지는 방식이 뭐임?",
            "confirmation": f"{context} {subject} {decision} 결정 여부, {condition_text}에 따라 달라지는 거 맞지?",
            "misconception": f"{context} {subject} {decision} 결정 여부도 {condition_text}에 따라 달라지는데, 조건 안 보고 정해도 됨?",
            "planning": f"{context} {subject} {decision} 결정하려면 {condition_text}에 따라 어떤 선택이 가능한지 확인할 필요 있음?",
            "evidence_check": f"{context} {subject} {decision} 결정 여부가 {condition_text}에 따라 달라지는지 확인할 수 있음?",
        }
    return templates[family]


def render_host_question(semantic: dict[str, Any], control: dict[str, Any]) -> str:
    """Render an E2 final question from host-owned slots only."""
    lane = semantic["target_outcome"]
    validate_renderer_control(control, lane)
    family = control["host_question_renderer"]["family"]
    if lane == "supported_answer":
        return _supported_question(semantic, control, family)
    return _clarification_question(semantic, control, family)
