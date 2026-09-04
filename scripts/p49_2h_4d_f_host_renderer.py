"""Frozen-infrastructure successor for the additive five-register tranche.

It reuses the reviewed E2 banmal renderer verbatim for its two banmal values
and owns final question wording for formal, polite, and conversational rows.
The E2 v1 renderer and its artifacts are not changed.
"""
from __future__ import annotations

from typing import Any

from scripts import p49_2h_4d_e2_host_renderer as e2
from scripts.p49_2h_register_taxonomy import CANONICAL_REGISTERS


RENDERER_ID = "P49-2H-4D-F-host-register-surface-v1"
FAMILIES = e2.FAMILIES
SUPPORTED_TOPICS = e2.SUPPORTED_TOPICS
CONTEXTS = e2.CONTEXTS


def validate_renderer_control(control: dict[str, Any], lane: str) -> None:
    renderer = control.get("host_question_renderer")
    if not isinstance(renderer, dict) or renderer.get("renderer_id") != RENDERER_ID:
        raise ValueError("unknown F host question renderer")
    if lane not in e2.SUPPORTED_LANES:
        raise ValueError("F host renderer is limited to supported/clarification lanes")
    if renderer.get("family") not in FAMILIES:
        raise ValueError("F host renderer family is unsupported")
    if control.get("register") not in CANONICAL_REGISTERS:
        raise ValueError("F host renderer requires a canonical register")
    if control.get("context_frame") not in CONTEXTS:
        raise ValueError("F host renderer context is unsupported")


def _supported_question(semantic: dict[str, Any], control: dict[str, Any], family: str) -> str:
    host = semantic["host_question_contract"]
    topic = SUPPORTED_TOPICS.get(host.get("canonical_requirement"))
    if topic is None:
        raise ValueError(f"F host renderer has no reviewed topic for {host.get('canonical_requirement')}")
    context, subject, register = CONTEXTS[control["context_frame"]], host["subject"], control["register"]
    templates = {
        "formal": {
            "direct": f"{context} {subject}의 {topic}은 무엇입니까?",
            "confirmation": f"{context} {subject}의 {topic}을 확인해야 합니까?",
            "misconception": f"{context} {subject}의 {topic}을 다른 기준으로 판단해도 됩니까?",
            "planning": f"{context} {subject}의 {topic}을 미리 어떻게 확인합니까?",
            "evidence_check": f"{context} {subject}의 {topic}은 제공 자료에서 확인할 수 있습니까?",
        },
        "polite": {
            "direct": f"{context} {subject}의 {topic}은 무엇인가요?",
            "confirmation": f"{context} {subject}의 {topic}을 확인해야 하나요?",
            "misconception": f"{context} {subject}의 {topic}을 다른 기준으로 판단해도 되나요?",
            "planning": f"{context} {subject}의 {topic}을 미리 어떻게 확인하나요?",
            "evidence_check": f"{context} {subject}의 {topic}은 제공 자료에서 확인할 수 있나요?",
        },
        "conversational": {
            "direct": f"{context} {subject}의 {topic}이 어떻게 되는지 알 수 있을까요?",
            "confirmation": f"{context} {subject}의 {topic}은 먼저 확인해 봐야 하나요?",
            "misconception": f"{context} {subject}의 {topic}을 다른 기준으로 보면 안 되는 건가요?",
            "planning": f"{context} {subject}의 {topic}을 미리 알아보려면 어떻게 하면 될까요?",
            "evidence_check": f"{context} {subject}의 {topic}은 자료에서 바로 확인할 수 있을까요?",
        },
    }
    return templates[register][family]


def _clarification_question(semantic: dict[str, Any], control: dict[str, Any], family: str) -> str:
    host = semantic["host_question_contract"]
    conditions = semantic["missing_conditions"]
    if not conditions:
        raise ValueError("F clarification renderer requires missing conditions")
    context, subject, decision = CONTEXTS[control["context_frame"]], host["subject"], semantic["decision_target"]
    condition_text = "와 ".join(conditions)
    register = control["register"]
    templates = {
        "formal": {
            "direct": f"{context} {subject}에서 {decision}의 결정 여부를 판단하려면 {condition_text}에 따라 어떤 점을 확인해야 합니까?",
            "confirmation": f"{context} {subject}의 {decision} 결정 여부는 {condition_text}에 따라 달라집니까?",
            "misconception": f"{context} {subject}에서 {decision}의 결정 여부를 {condition_text} 없이 정해도 됩니까?",
            "planning": f"{context} {subject}의 {decision}를 정하려면 {condition_text}에 따라 어떤 선택이 가능한지 확인해야 합니까?",
            "evidence_check": f"{context} {subject}의 {decision} 결정 여부가 {condition_text}에 따라 달라지는지 확인할 수 있습니까?",
        },
        "polite": {
            "direct": f"{context} {subject}에서 {decision}의 결정 여부를 보려면 {condition_text}에 따라 어떤 점을 확인해야 하나요?",
            "confirmation": f"{context} {subject}의 {decision} 결정 여부는 {condition_text}에 따라 달라지나요?",
            "misconception": f"{context} {subject}에서 {decision}의 결정 여부를 {condition_text} 없이 정해도 되나요?",
            "planning": f"{context} {subject}의 {decision}를 정하려면 {condition_text}에 따라 어떤 선택이 가능한지 확인해야 하나요?",
            "evidence_check": f"{context} {subject}의 {decision} 결정 여부가 {condition_text}에 따라 달라지는지 확인할 수 있나요?",
        },
        "conversational": {
            "direct": f"{context} {subject}에서 {decision}의 결정 여부를 보려면 {condition_text}에 따라 무엇을 봐야 할까요?",
            "confirmation": f"{context} {subject}의 {decision} 결정 여부는 {condition_text}에 따라 달라지는 건가요?",
            "misconception": f"{context} {subject}에서 {decision}의 결정 여부를 {condition_text} 없이 정하면 안 되나요?",
            "planning": f"{context} {subject}의 {decision}를 정할 때 {condition_text}에 따라 어떤 선택이 가능한지 알 수 있을까요?",
            "evidence_check": f"{context} {subject}의 {decision} 결정 여부가 {condition_text}에 따라 달라지는지 자료에서 확인할 수 있을까요?",
        },
    }
    return templates[register][family]


def render_host_question(semantic: dict[str, Any], control: dict[str, Any]) -> str:
    """Render a final question from host-owned slots; HCX wording is audit-only."""
    validate_renderer_control(control, semantic["target_outcome"])
    if control["register"] in {"casual_banmal", "terse_banmal"}:
        # E2's approved banmal morphology is deliberately reused rather than
        # reimplemented in the additive path.
        e2_control = {**control, "host_question_renderer": {
            "renderer_id": e2.RENDERER_ID,
            "family": control["host_question_renderer"]["family"],
        }}
        return e2.render_host_question(semantic, e2_control)
    family = control["host_question_renderer"]["family"]
    if semantic["target_outcome"] == "supported_answer":
        return _supported_question(semantic, control, family)
    return _clarification_question(semantic, control, family)


def surface_findings(question: str, semantic: dict[str, Any], control: dict[str, Any]) -> list[str]:
    """Check final surface without changing the semantic validator's policy."""
    compact = "".join(question.lower().split())
    host = semantic["host_question_contract"]
    subject = host["subject"].replace("제도", "").replace("만기자금", "").strip()
    aliases = {"".join(alias.lower().split()) for alias in host.get("request_local_subject_aliases", [])}
    aliases.add("".join(subject.lower().split()))
    findings: list[str] = []
    if not any(alias and alias in compact for alias in aliases):
        findings.append("register_subject_loss")
    register = control["register"]
    endings = {
        "formal": ("습니까?", "합니까?", "됩니까?", "입니까?"),
        "polite": ("요?", "나요?", "되나요?"),
        "conversational": ("요?", "까요?"),
        "casual_banmal": ("야?", "거야?", "맞아?", "돼?", "있어?", "해?", "될까?", "인가?"),
        "terse_banmal": ("임?", "맞지?", "됨?", "몰라?", "있음?"),
    }
    if not any(compact.endswith(ending) for ending in endings[register]):
        findings.append("register_surface_drift")
    return sorted(set(findings))
