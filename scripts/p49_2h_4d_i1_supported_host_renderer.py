"""Additive, fail-closed supported question surfaces for I1 only."""
from __future__ import annotations
from typing import Any

RENDERER_ID = "P49-2H-4D-I1-supported-host-surface-v1"
TOPICS = {
    "IRP.early_withdrawal.allowed_reasons": "중도인출이 가능한 법정 사유",
    "DC.early_withdrawal.required_documents": "중도인출에 필요한 서류",
    "product.risk_grade.current": "현재 위험등급",
    "product.total_fee": "총보수율",
    "product.period_cost": "해당 기간별 보유 비용",
    "product.risk_grade.historical": "과거 위험등급 변경 이력",
    "product.tracking_index": "추종하는 지수",
    "ISA.transfer.deadline": "만기자금 이전 기한",
    "product.equity_allocation_limit": "주식형 자산 편입 한도",
}

def render_host_question(semantic: dict[str, Any], control: dict[str, Any]) -> str:
    host = semantic["host_question_contract"]
    requirement = host.get("canonical_requirement")
    if semantic["target_outcome"] != "supported_answer" or requirement not in TOPICS:
        raise ValueError(f"I1 renderer is fail-closed for {requirement}")
    renderer = control.get("host_question_renderer", {})
    if renderer.get("renderer_id") != RENDERER_ID:
        raise ValueError("unknown I1 renderer control")
    family = renderer.get("family")
    if family not in {"direct", "confirmation", "misconception", "planning", "evidence_check"}:
        raise ValueError("unsupported I1 question family")
    subject, topic = host["subject"], TOPICS[requirement]
    if requirement == "product.total_fee" and family == "direct":
        # A total-fee requirement is numeric.  Keep its direct surface a
        # value question rather than a generic definition question.
        return f"{subject}의 {topic}은 얼마입니까?"
    templates = {
        "direct": f"{subject}의 {topic}은 무엇입니까?",
        "confirmation": f"{subject}의 {topic}을 확인해야 합니까?",
        "misconception": f"{subject}의 {topic}을 다른 기준으로 판단해도 됩니까?",
        "planning": f"{subject}의 {topic}을 미리 어떻게 확인합니까?",
        "evidence_check": f"{subject}의 {topic}은 제공 자료에서 확인할 수 있습니까?",
    }
    return templates[family]

def surface_findings(question: str, semantic: dict[str, Any]) -> list[str]:
    host = semantic["host_question_contract"]; compact = "".join(question.lower().split())
    subject = "".join(host["subject"].lower().split())
    topic = "".join(TOPICS[host["canonical_requirement"]].lower().split())
    findings=[]
    if subject not in compact: findings.append("register_subject_loss")
    if topic not in compact: findings.append("supported_question_scope_drift")
    return findings
