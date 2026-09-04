"""Run P49-2H-3C only with explicit authorization for 35 HCX-007 calls.

The v2 runner intentionally separates supported, clarification, and bounded
schemas.  It never touches the browser runtime and never promotes candidate
status beyond ``generated/pending/not_accepted``.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.p49_2h_register_taxonomy import BANMAL_REGISTERS, REGISTER_RULES
from src.augmentation.hcx_structured_generator import HCXStructuredAugmentationGenerator
from src.config.generation import GenerationSettings
from scripts.validate_p49_2h_contract_split_micro_pilot import (
    FROZEN_SEED,
    CORPUS,
    read_jsonl as read_validation_jsonl,
    similarity,
    subject_contract_for_evidence,
    validate,
)


SUPPORTED_SCHEMA = {
    "type": "object", "properties": {
        "question": {"type": "string"}, "modifiers": {"type": "object"},
        "required_gold_facts": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "evidence_literal_quotes": {"type": "array", "items": {"type": "string"}},
        }, "required": ["text", "evidence_literal_quotes"]}},
        "answer_text": {"type": "string"},
    }, "required": ["question", "modifiers", "required_gold_facts", "answer_text"],
}
CLARIFICATION_SCHEMA = {
    "type": "object", "properties": {
        "question": {"type": "string"}, "modifiers": {"type": "object"},
        "clarification_questions": {"type": "array", "items": {"type": "string"}},
    }, "required": ["question", "modifiers", "clarification_questions"],
}
BOUNDED_SCHEMA = {
    "type": "object", "properties": {
        "question": {"type": "string"}, "modifiers": {"type": "object"},
        "supported_gold_facts": {"type": "array", "items": {"type": "object", "properties": {
            "text": {"type": "string"}, "evidence_literal_quotes": {"type": "array", "items": {"type": "string"}},
        }, "required": ["text", "evidence_literal_quotes"]}},
        "supported_answer_text": {"type": "string"},
    }, "required": ["question", "modifiers", "supported_gold_facts", "supported_answer_text"],
}


# Bounded responses are safety outcomes, not a place for the model to choose
# which surrounding sentence from a chunk becomes user-facing prose.  The
# rendered factual part is deliberately owned by the canonical requirement.
# New bounded requirements must add an explicit renderer before they enter a
# generation lane.
BOUNDED_HOST_FACTUAL_RENDERERS = {
    "ISA.transfer.additional_tax_credit": "ISA 만기자금을 연금계좌에 넣으면 이전 금액의 10%, 최대 300만원까지 추가 세액공제 대상이 됩니다.",
    "product.risk_grade.current": "현재 위험등급은 2등급(높은위험)입니다.",
    "product.risk_grade.change_possibility": "이 상품의 위험등급은 운용실적과 시장 상황 등에 따라 변경될 수 있습니다.",
    "product.total_fee": "총보수는 지급비율(연간, %) 표의 총보수·비용 항목에서 클래스별로 확인합니다.",
}


# Supported records normally keep the HCX prose candidate, but a requirement
# with multiple mandatory factual axes may use a host renderer when repeated
# generation omits one direct-evidence axis.  This is keyed by canonical
# requirement—not by an individual question—and remains fully evidence-bound.
SUPPORTED_HOST_FACTUAL_RENDERERS = {
    "DB.operation_party": "DB제도 적립금의 운용 주체는 회사입니다.",
    "DB.benefit_determination": "DB형 퇴직급여는 퇴직 전 평균임금 30일분과 계속근로기간을 기준으로 계산합니다.",
    "DC.operation_party": "DC제도 적립금은 근로자가 운용합니다.",
    "DC.employer_contribution": "DC제도에서 회사 부담금 기준은 연간임금총액의 1/12 이상입니다.",
    "retirement_income.IRP_transfer.tax_timing": (
        "연금으로 수령하면 운용수익은 연금 수령 시까지 과세이연되고, "
        "세금 납부는 연금 수령 시마다 분산됩니다. 일시금 수령 시에는 퇴직 즉시 납부합니다."
    ),
    "pension_savings.tax_credit.limit": "연금저축만 납입하는 경우 세액공제 대상 납입 한도는 연 600만원입니다.",
    "ISA.transfer.deadline": "ISA 만기자금은 만기 후 60일 내에 연금계좌로 옮길 수 있습니다.",
    "ISA.transfer.additional_tax_credit": "ISA 만기자금을 연금계좌에 넣으면 이전 금액의 10%, 최대 300만원까지 추가 세액공제 대상이 됩니다.",
    "DC.early_withdrawal.allowed_reasons": "DC제도는 주택 구입 등 대통령령이 정하는 사유가 발생한 경우 중도인출이 허용됩니다.",
    "DC.early_withdrawal.required_documents": (
        "6개월 이상 요양 사유의 DC 중도인출에는 신청양식과 진단서 또는 소견서가 필요합니다. "
        "상황에 따라 장기요양확인서, 연간임금총액 확인서류 및 의료비 지출 증빙도 함께 제출합니다."
    ),
    "product.risk_grade.current": "현재 투자 위험 등급은 2등급(높은위험)입니다.",
    "product.risk_grade.change_possibility": "이 상품의 위험등급은 운용실적과 시장 상황 등에 따라 변경될 수 있습니다.",
    "product.risk_grade.historical": (
        "위험등급은 2016년 분류체계 개편으로 1등급에서 3등급으로, 2021년에 3등급에서 2등급으로, "
        "2024년에 2등급에서 3등급으로, 2025년에는 VaR 기준 변경에 따라 3등급에서 2등급으로 변경된 이력이 있습니다."
    ),
    "product.total_fee": "총보수는 지급비율(연간, %) 표의 총보수·비용 항목에서 클래스별로 확인합니다.",
    "product.period_cost": "1,000만원 투자 시 투자기간별 예시 표에서 1년·3년·5년·10년 비용을 클래스별로 확인할 수 있습니다.",
}


SUPPORTED_HOST_QUESTION_RENDERERS = {
    "DC.early_withdrawal.required_documents": "DC에서 6개월 이상 요양 사유로 중도인출하려면 어떤 서류가 필요한가요?",
    "product.risk_grade.historical": "한국투자 골드플랜 연금 증권 전환형 투자신탁 1호(주식)의 과거 투자 위험 등급 이력은 어떻게 되나요?",
    "product.total_fee": "이 상품의 총보수는 어느 표의 어떤 항목에서 확인하나요?",
    "product.period_cost": "1,000만원 투자 시 기간별 비용 예시는 어떻게 확인하나요?",
}


# P49-2H-4D-C uses this additional host-owned block only for an additive,
# bounded-answer targeted manifest.  It gives duplicate-heavy cells wording
# dimensions which are more specific than the original four generic controls;
# it never changes a semantic slot, evidence binding, or answer contract.
BOUNDED_TARGETED_PROFILE_FIELDS = (
    "profile_id",
    "user_situation_frame",
    "speech_act",
    "information_gap_mode",
    "temporal_expression",
    "misconception_type",
    "sentence_shape",
)
BOUNDED_LINGUISTIC_ANCHOR_FIELDS = (
    "anchor_id",
    "anchor_question",
    "linguistic_archetype",
    "authoring_status",
    "human_review_status",
)


def bounded_linguistic_anchor_instruction(request: dict) -> str | None:
    """Bind an approved bounded linguistic anchor as an anti-paraphrase cue."""
    control = request.get("remediation_control") or {}
    anchor = control.get("bounded_linguistic_anchor")
    if anchor is None:
        return None
    lane = request.get("contract_lane", request.get("target_outcome"))
    if lane != "bounded_answer":
        raise ValueError("bounded linguistic anchor is only valid for bounded_answer")
    missing = [field for field in BOUNDED_LINGUISTIC_ANCHOR_FIELDS if not anchor.get(field)]
    if missing:
        raise ValueError("bounded linguistic anchor is incomplete: " + ", ".join(missing))
    return "\n".join(
        [
            "[P49-2H-4D-D bounded linguistic anchor — host-owned]",
            f"anchor_id={anchor['anchor_id']}",
            f"anchor_question={anchor['anchor_question']}",
            f"linguistic_archetype={anchor['linguistic_archetype']}",
            "이 anchor는 새로운 사용자 상황·화행·정보 공백·시간 표현·오해 전제·문장 구조를 보여 주는 언어적 기준입니다.",
            "anchor 질문을 복사하거나 어순만 바꾼 paraphrase로 만들지 마세요. 같은 host-owned semantic slots를 유지하되, anchor와도 기존 비교 질문과도 다른 표면 실현을 생성하세요.",
            "anchor는 factual claim이나 evidence가 아닙니다. subject, unsupported target, temporal scope, target type, concreteness requirement, supported requirements를 바꾸거나 넓히지 마세요.",
        ]
    )


def bounded_targeted_diversity_instruction(request: dict) -> str | None:
    """Render an active, validated v6 bounded diversity profile.

    The values are deliberately finite host-owned categories.  This lets the
    preflight prove that each selected wording dimension is active in the HCX
    prompt while keeping future/unsupported semantic slots untouched.
    """
    control = request.get("remediation_control") or {}
    profile = control.get("bounded_diversity_profile")
    if profile is None:
        return None
    lane = request.get("contract_lane", request.get("target_outcome"))
    if lane != "bounded_answer":
        raise ValueError("bounded targeted diversity profile is only valid for bounded_answer")
    missing = [field for field in BOUNDED_TARGETED_PROFILE_FIELDS if not profile.get(field)]
    if missing:
        raise ValueError("bounded targeted diversity profile is incomplete: " + ", ".join(missing))

    situation_rules = {
        "공시자료 검토 중": "질문의 첫 절에 공시자료를 읽으며 미래 정보의 범위를 확인하는 상황을 자연스럽게 드러내세요.",
        "계약 체결 직전": "질문의 첫 절에 계약 체결 직전 필요한 정보의 확정 여부를 확인하는 상황을 자연스럽게 드러내세요.",
        "정기 점검 중": "질문의 첫 절에 정기 점검 중 향후 정보를 다시 확인하는 상황을 자연스럽게 드러내세요.",
        "운용 변경 안내 확인 중": "질문의 첫 절에 변경 안내를 확인하며 미래의 구체값을 확인하려는 상황을 자연스럽게 드러내세요.",
        "장기 보유 계획 중": "질문의 첫 절에 장기 보유 계획을 세우며 미래 정보의 확정 여부를 확인하는 상황을 자연스럽게 드러내세요.",
        "연말 자금 계획 중": "질문의 첫 절에 연말 자금 계획을 세우며 향후 정보를 확인하는 상황을 자연스럽게 드러내세요.",
    }
    speech_rules = {
        "자료 범위 확인": "제공 자료가 미래의 구체값까지 확인해 주는지를 묻는 질문 행위를 사용하세요.",
        "확정 여부 확인": "미래의 구체값이 이미 확정되었는지를 확인하는 질문 행위를 사용하세요.",
        "계획 전제 점검": "계획을 세우기 전에 미래 정보가 확정값인지 점검하는 질문 행위를 사용하세요.",
        "오해 전제 확인": "사용자의 잘못된 확정 전제를 자연스럽게 드러내고 확인하는 질문 행위를 사용하세요.",
    }
    gap_rules = {
        "현재 정보와 미래 확정값 구분": "현재 자료가 미래의 구체값을 보장하지 않는다는 정보 공백을 질문에 반영하세요.",
        "근거 범위 점검": "제공된 근거가 미래의 구체값을 어디까지 뒷받침하는지 확인하는 방식으로 질문하세요.",
        "미래 수치 미확정 점검": "미래의 구체 수치·등급·한도가 확정됐다는 전제를 확인하는 방식으로 질문하세요.",
    }
    misconception_rules = {
        "미래 값이 이미 확정됐다는 전제": "미래의 구체값이 이미 정해졌다고 단정하지 말고, 그 전제가 맞는지 묻는 형태로만 사용하세요.",
        "현재 정보가 미래 값을 보장한다는 전제": "현재 정보에서 미래 값이 자동으로 나온다고 단정하지 말고, 그 전제가 맞는지 묻는 형태로만 사용하세요.",
        "향후 시점에도 같은 값이라는 전제": "향후에도 같은 구체값이 유지된다고 단정하지 말고, 그 전제가 맞는지 묻는 형태로만 사용하세요.",
    }
    shape_rules = {
        "상황절+근거범위 확인": "상황절 뒤에 자료 또는 근거 범위를 확인하는 한 문장 질문으로 구성하세요.",
        "상황절+확정전제 확인": "상황절 뒤에 미래 구체값의 확정 전제를 확인하는 한 문장 질문으로 구성하세요.",
        "계획절+정보공백 확인": "계획 상황을 짧게 제시한 뒤 미래 정보 공백을 확인하는 한 문장 질문으로 구성하세요.",
    }
    try:
        situation_rule = situation_rules[profile["user_situation_frame"]]
        speech_rule = speech_rules[profile["speech_act"]]
        gap_rule = gap_rules[profile["information_gap_mode"]]
        misconception_rule = misconception_rules[profile["misconception_type"]]
        shape_rule = shape_rules[profile["sentence_shape"]]
    except KeyError as exc:
        raise ValueError(f"unsupported bounded targeted diversity profile: {exc.args[0]}") from exc
    # These exact markers are already required by the unchanged bounded
    # semantic validator.  Reject an attractive but validator-invisible time
    # synonym at preflight rather than spending an HCX call on guaranteed
    # temporal drift.
    if profile["temporal_expression"] not in {"앞으로", "향후", "미래", "다음"}:
        raise ValueError("bounded targeted temporal expression is not validator-compatible")

    return "\n".join(
        [
            "[P49-2H-4D-C bounded targeted diversity profile — host-owned]",
            "아래 profile은 질문의 사용자 상황과 화행만 바꿉니다. unsupported target, temporal scope, target type, concreteness requirement, supported requirements, subject, evidence를 추가·삭제·변경하지 마세요.",
            f"bounded_profile_id={profile['profile_id']}",
            f"user_situation_frame={profile['user_situation_frame']}: {situation_rule}",
            f"speech_act={profile['speech_act']}: {speech_rule}",
            f"information_gap_mode={profile['information_gap_mode']}: {gap_rule}",
            f"temporal_expression={profile['temporal_expression']}: 질문에 이 시간 표현을 자연스럽게 포함하세요.",
            f"misconception_type={profile['misconception_type']}: {misconception_rule}",
            f"sentence_shape={profile['sentence_shape']}: {shape_rule}",
        ]
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def schema_for(request: dict) -> dict:
    return {"supported_answer": SUPPORTED_SCHEMA, "clarification_required": CLARIFICATION_SCHEMA, "bounded_answer": BOUNDED_SCHEMA}[request["contract_lane"]]


def remediation_diversity_instruction(request: dict) -> str | None:
    """Bind 4B diversity controls to question wording without changing its facts.

    Regular v4 requests deliberately retain their frozen prompt.  A 4B
    remediation request carries an additional host-owned ``remediation_control``
    block, which must affect the model-owned question wording or it cannot
    improve diversity against the immutable comparison pool.
    """
    control = request.get("remediation_control")
    if control is None:
        return None
    required = ("context_frame", "query_form", "register", "length_band")
    missing = [field for field in required if not control.get(field)]
    if missing:
        raise ValueError("remediation diversity control is incomplete: " + ", ".join(missing))

    context_rules = {
        "이직/퇴직 직후": ("질문의 첫 절에 ‘퇴직 직후’를 반드시 넣고, 그 시점에 퇴직급여·계좌 처리를 정해야 하는 상황을 "
                         "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "이전 신청 중": ("질문의 첫 절에 ‘이전 신청’을 반드시 넣고, 실제 신청·진행 중 필요한 판단이라는 점을 "
                    "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "상담 전 확인": ("질문의 첫 절에 ‘상담 전’을 반드시 넣고, 본인의 상황을 확인하려는 목적을 "
                    "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "상품 비교 전 확인": ("질문의 첫 절에 ‘상품 비교 전’을 반드시 넣고, 비교 전에 확인해야 하는 상황·판단 목적을 "
                       "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "세액공제 계산 전": ("질문의 첫 절에 ‘세액공제 계산 전’을 반드시 넣고, 계산 전에 확인하려는 상황·판단 목적을 "
                      "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "서류 준비 중": ("질문의 첫 절에 ‘서류 준비’를 반드시 넣고, 신청 서류를 준비·제출하기 전 확인하려는 상황을 "
                   "decision target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "공시자료 검토 중": ("질문의 첫 절에 ‘공시자료’를 반드시 넣고, 공시자료를 읽으며 확인하려는 실제 상황을 "
                       "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "계약 체결 직전": ("질문의 첫 절에 ‘계약 체결 직전’을 반드시 넣고, 체결 전에 확인하려는 상황을 "
                      "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "정기 점검 중": ("질문의 첫 절에 ‘정기 점검’을 반드시 넣고, 보유·계획 정보를 다시 확인하려는 상황을 "
                    "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "운용 변경 안내 확인 중": ("질문의 첫 절에 ‘변경 안내’를 반드시 넣고, 안내 내용을 확인하려는 상황을 "
                          "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "장기 보유 계획 중": ("질문의 첫 절에 ‘장기 보유 계획’을 반드시 넣고, 계획을 세우며 확인하려는 상황을 "
                       "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
        "연말 자금 계획 중": ("질문의 첫 절에 ‘연말 자금 계획’을 반드시 넣고, 자금 계획을 세우며 확인하려는 상황을 "
                       "target과 연결해 자연스럽게 드러내세요. 단어만 장식처럼 덧붙이지 마세요."),
    }
    query_rules = {
        "direct": (
            "부연 설명형이 아니라 필요한 판단·정보를 한 번에 직접 묻는 질문 구조를 사용하세요. "
            "첫 절은 context_frame의 실제 상황, 다음 절은 decision target, 마지막 절은 missing condition 또는 target을 "
            "‘먼저 무엇을 확인해야 하는가’로 묻는 구조로 역할을 분리하세요. "
            "모든 조건을 나열한 뒤 ‘따라 달라지는지’만 묻는 문장 구조는 사용하지 마세요."
        ),
        "confirmation": "사용자가 알고 있는 전제나 예상이 맞는지 확인하는 질문 구조를 사용하세요.",
        "misconception": "잘못 이해했을 수 있는 전제를 질문 안에 자연스럽게 드러내고 확인하는 질문 구조를 사용하세요.",
        "conditional": "명시된 조건에 따라 결과가 달라지는지를 묻는 질문 구조를 사용하세요.",
        "numeric": "숫자·한도·등급·시점처럼 구체적인 값을 묻는 질문 구조를 사용하세요.",
        "evidence_limit": "제공 자료가 미래의 구체값까지 알려 주는지 근거 범위를 확인하는 질문 구조를 사용하세요.",
        "planning_check": "계획을 세우기 전에 미래의 구체값이 확정 정보인지 점검하는 질문 구조를 사용하세요.",
        "assumption_check": "미래의 구체값이 이미 정해졌다는 사용자의 전제가 맞는지 확인하는 질문 구조를 사용하세요.",
    }
    length_rules = {
        "short": "짧은 한 문장으로 작성하고, 같은 뜻의 설명을 덧붙이거나 반복하지 마세요.",
        "medium": "한 문장 또는 짧은 두 절로 작성하되, 상황과 질문 목적이 모두 드러나게 하세요.",
    }
    try:
        context_rule = context_rules[control["context_frame"]]
        query_rule = query_rules[control["query_form"]]
        register_rule = REGISTER_RULES[control["register"]]
        length_rule = length_rules[control["length_band"]]
    except KeyError as exc:
        raise ValueError(f"unsupported remediation diversity control: {exc.args[0]}") from exc

    instruction_lines = [
            "[P49-2H-4C remediation diversity controls — host-owned]",
            "질문의 factual intent와 host-owned semantic slots는 바꾸지 마세요. 숫자·상품명·subject·requirement·missing condition·unsupported target·근거 범위를 추가·삭제·변경하지 마세요.",
            f"context_frame={control['context_frame']}: {context_rule}",
            f"query_form={control['query_form']}: {query_rule}",
            f"register={control['register']}: {register_rule}",
            f"length_band={control['length_band']}: {length_rule}",
        ]
    if control["register"] in BANMAL_REGISTERS:
        subject = str(control.get("subject") or "host-owned subject")
        if control["register"] == "casual_banmal":
            ending_rule = "~야?, ~거야?, ~맞아?, ~되는 거야? 계열의 자연스러운 반말 의문형"
        else:
            # Keep the prompt aligned to the immutable register surface
            # validator.  This is wording policy only; it does not change a
            # semantic slot or validator threshold.
            ending_rule = "~임?, ~맞지?, ~됨?, ~몰라?, ~있음? 계열의 짧은 반말 확인형"
        instruction_lines.extend(
            [
                "[P49-2H-4D-E1 banmal subject and surface binding — host-owned]",
                f"banmal_subject_binding: subject={subject}",
                "question에는 위 subject 또는 host question semantic contract가 허용한 subject alias를 반드시 한 번 이상 명시하세요. "
                "‘그거’, ‘이거’, ‘그 상품’, ‘그건’ 같은 대명사만으로 subject를 대체하거나 subject를 생략·변경하지 마세요.",
                f"banmal_register_surface={control['register']}: 종결은 {ending_rule}만 사용하세요. "
                "존댓말(~요?, ~습니다?)과 서술형 종결은 금지합니다. 짧은 반말이라도 subject·수치·조건·기간 등 host-owned semantic slot을 제거하지 마세요.",
            ]
        )
    instruction_lines.append(
        "immutable comparison pool의 기존 질문을 단순히 어순만 바꾼 paraphrase로 만들지 마세요. 동일 coverage cell이라도 위 상황과 판단 목적이 질문에 실제로 드러나야 합니다."
    )
    instruction = "\n".join(instruction_lines)
    targeted = bounded_targeted_diversity_instruction(request)
    anchor = bounded_linguistic_anchor_instruction(request)
    return "\n".join(item for item in (instruction, targeted, anchor) if item)


def banmal_final_question_check_instruction(request: dict) -> str | None:
    """Repeat E1's two banmal controls beside the lane-output contract.

    The diversity instruction remains the canonical host-owned control.  This
    short final checklist merely prevents the much later evidence/clarification
    payload from making HCX lose the subject or requested surface form.
    """
    control = request.get("remediation_control") or {}
    register = control.get("register")
    if register not in BANMAL_REGISTERS:
        return None
    subject = str(control.get("subject") or "host-owned subject")
    endings = (
        "~야?, ~거야?, ~맞아?, ~되는 거야?"
        if register == "casual_banmal"
        else "~임?, ~맞지?, ~됨?, ~몰라?, ~있음?"
    )
    return "\n".join(
        [
            "[P49-2H-4D-E1 final question check — host-owned]",
            f"banmal_final_question_check: subject={subject}; register={register}",
            f"JSON을 반환하기 직전 question에 `{subject}` 또는 허용된 subject alias가 실제로 한 번 이상 있는지 확인하세요. "
            "‘그거’, ‘이거’, ‘그 상품’, ‘그건’만으로 subject를 대신한 question은 반환하지 마세요.",
            f"question의 마지막은 {endings} 중 validator가 인식하는 반말 의문 종결로 끝내고, 존댓말·서술형 종결로 바꾸지 마세요.",
        ]
    )


def supported_answer_completeness_instruction(request: dict) -> str | None:
    """Render the opt-in E2A answer-completeness binding from host facts.

    The binding is intentionally unavailable to every other requirement.  It
    copies no new fact into the contract: all required terms and literal
    evidence quotes must already be present in the immutable v4 request.
    """
    control = request.get("remediation_control") or {}
    binding = control.get("supported_answer_completeness")
    if binding is None:
        return None
    if request.get("contract_lane") != "supported_answer":
        raise ValueError("supported answer completeness is only valid for supported_answer")
    semantic = request.get("semantic_request") or {}
    canonical = semantic.get("host_question_contract", {}).get("canonical_requirement")
    if binding.get("canonical_requirement") != canonical:
        raise ValueError("supported answer completeness canonical requirement mismatch")
    expected_terms = request.get("answer_contract", {}).get("required_terms", [])
    expected_quotes = request.get("literal_evidence_quotes", [])
    if binding.get("required_answer_terms") != expected_terms:
        raise ValueError("supported answer completeness required terms mismatch")
    if binding.get("required_literal_quotes") != expected_quotes:
        raise ValueError("supported answer completeness literal quotes mismatch")
    if not expected_terms or not expected_quotes:
        raise ValueError("supported answer completeness requires non-empty host facts")
    return "\n".join(
        [
            "[P49-2H-4D-E2A supported answer completeness — host-owned]",
            f"canonical_requirement={canonical}",
            "answer_text는 아래 host-required answer terms와 direct-evidence literal quotes를 빠짐없이 모두 명시해야 합니다. "
            "하나라도 빠지면 JSON을 반환하지 말고 answer_text를 다시 완성하세요.",
            "required_answer_terms=" + json.dumps(expected_terms, ensure_ascii=False),
            "required_literal_quotes=" + json.dumps(expected_quotes, ensure_ascii=False),
            "이 목록은 닫힌 completeness contract입니다. 목록 밖의 인접 field·예측·추천·근거 밖 설명을 추가하지 마세요.",
        ]
    )


def remediation_field_boundary_instruction(request: dict) -> str | None:
    """Bind a supported remediation question to its one host-owned field.

    This is intentionally limited to the 4B remediation supported-answer
    path.  Frozen non-remediation, clarification, and bounded prompts retain
    their existing contracts.  Diversity may change wording and user context,
    never the semantic field being asked about.
    """
    if request.get("contract_lane") != "supported_answer" or not request.get("remediation_control"):
        return None
    semantic = request.get("semantic_request")
    if not semantic:
        return None
    contract = semantic["host_question_contract"]
    allowed_fields = contract["allowed_fields"]
    forbidden_fields = semantic["forbidden_fields"]
    return "\n".join(
        [
            "[P49-2H-4D remediation field-boundary controls]",
            "질문의 semantic scope는 아래 allowed_fields의 단일 field로 고정합니다: " + ", ".join(allowed_fields),
            "allowed_fields 밖에서 같은 주제와 함께 자주 언급되는 field라도 질문에 추가하거나 비교하지 마세요.",
            "아래 forbidden_fields는 질문의 부연 주제·비교 대상·답변 요구로 포함하지 마세요: " + "; ".join(forbidden_fields),
            "한 field를 여러 field의 합산 한도나 각각의 한도로 확장하지 마세요. ‘각각 얼마인지’처럼 복수 field를 묻는 구조는 금지합니다.",
            "context_frame, query_form, register, length_band는 표현과 사용자 상황에만 사용하고 semantic scope는 바꾸지 마세요.",
        ]
    )


def build_payload(request: dict, previous_questions: list[str], retry_findings: list[str] | None = None) -> dict:
    lane = request["contract_lane"]
    diversity = json.dumps(previous_questions[-8:], ensure_ascii=False)
    common = [
        "반환 JSON의 question은 실제 한국어 사용자가 입력할 자연스러운 질문 한 문장만 작성하세요.",
        "작업 지시, P49, JSON, chunk_id, 원본 근거라는 말을 question에 넣지 마세요.",
        f"augmentation type: {request['augmentation_type']}",
        f"최근 생성 질문과 같은 문장을 반복하지 마세요: {diversity}",
    ]
    if retry_findings:
        common.append(
            "이전 시도는 아래 host validator에서 실패했습니다. 같은 실패를 반복하지 말고, "
            "host가 정한 field와 outcome만 지키세요: " + ", ".join(retry_findings)
        )
    diversity_instruction = remediation_diversity_instruction(request)
    if diversity_instruction:
        common.append(diversity_instruction)
    semantic = request.get("semantic_request")
    if semantic:
        contract = semantic["host_question_contract"]
        semantic_rule = [
            "[Host-owned question semantic contract]",
            f"subject: {contract['subject']}", f"scope: {contract['question_scope']}",
            f"allowed_fields: {', '.join(contract['allowed_fields'])}",
            f"forbidden_fields: {', '.join(semantic['forbidden_fields'])}",
        ]
        if semantic["target_outcome"] == "clarification_required":
            semantic_rule.extend([
                "질문은 일반 절차·고려사항 질문이 아니라 조건 부족형 결정 질문이어야 합니다.",
                "decision_target: " + semantic["decision_target"],
                "scenario_context: " + semantic["scenario_context"],
                "질문 안에서 반드시 '...에 따라/경우에 따라/달라지는지'처럼 다음 조건에 의존한다는 뜻을 표현하세요: " + ", ".join(semantic["missing_conditions"]),
                "'고려할 사항', '일반적으로 어떻게', '절차', '필요한 서류'만 묻는 질문은 금지합니다.",
            ])
        if semantic["target_outcome"] == "bounded_answer":
            semantic_rule.extend([
                "질문은 반드시 이 미지원 target의 미래·예측 값을 실제로 요구해야 합니다: " + semantic["unsupported_target"],
                "temporal_scope: " + contract["temporal_scope"],
                "target_type: " + contract["target_type"],
                "concreteness_requirement: " + contract["concreteness_requirement"],
                "현재 값 질문이나 단순 변경 가능성 질문은 금지합니다. 미래의 구체 값·등급·시점을 물어야 합니다.",
            ])
        common.append("\n".join(semantic_rule))
    field_boundary_instruction = remediation_field_boundary_instruction(request)
    if field_boundary_instruction:
        common.append(field_boundary_instruction)
    if lane == "supported_answer":
        evidence = request["direct_evidence"][0]
        text = common + [
            "[지원형 계약] 질문과 답변은 아래 requirement의 direct evidence만 사용합니다.",
            "evidence_literal_quotes에는 아래 evidence_text에 실제로 존재하는 짧은 원문 문자열만 넣으세요. chunk_id는 quote가 아닙니다.",
            "모든 required_gold_facts는 답변에 필요한 사실만 포함합니다. evidence_literal_quotes는 host가 검증하므로 임의의 ID·새 문자열을 넣지 마세요.",
            "answer_text에는 답변 본문만 넣으세요. [답변]/[근거]/[유의사항] label, 투자 조언, 조건·세율·기한·예외 같은 direct evidence 밖 정보는 넣지 마세요.",
            "answer_text는 required literal evidence quotes에 있는 핵심 사실을 빠짐없이 직접 설명해야 합니다.",
            "requirement: " + request["requirements"][0]["canonical_requirement"],
            "semantic focus: " + request["semantic_focus"],
            "variation control: " + json.dumps(request["variation_control"], ensure_ascii=False),
            "다른 requirement를 함께 묻거나 답하지 말고 semantic focus 하나만 유지하세요.",
            "field constraints: " + json.dumps(request["field_constraints"], ensure_ascii=False),
            "required literal evidence quotes: " + json.dumps(request["literal_evidence_quotes"], ensure_ascii=False),
            "evidence_text:\n" + evidence["text"],
        ]
        completeness_instruction = supported_answer_completeness_instruction(request)
        if completeness_instruction:
            text.append(completeness_instruction)
    elif lane == "clarification_required":
        text = common + [
            "[재질문형 계약] 아래 사용자 상황은 핵심 조건이 부족합니다. 문서의 사실을 답하지 말고, missing_conditions를 확인하는 최소 재질문만 작성하세요.",
            "근거 인용이나 답변 completion을 만들지 마세요. clarification_questions에는 실제로 물어볼 조건만 넣으세요.",
            "user_question_scenario: " + request["user_question_scenario"],
            "missing_conditions: " + json.dumps(request["missing_conditions"], ensure_ascii=False),
        ]
    else:
        evidence_rows = request["direct_evidence"]
        evidence_text = evidence_rows[0]["text"] if evidence_rows else "(직접 근거 없음)"
        text = common + [
            "[제한답변형 계약] unsupported_target의 미래/예측값은 제공 근거에 없습니다. 그 값을 예측하거나 수치로 만들지 마세요.",
            "direct evidence가 있는 경우에만 그것이 지지하는 현재/일반 사실을 supported_gold_facts와 supported_answer_text에 포함하세요. unsupported value는 절대 쓰지 마세요.",
            "supported_answer_text에는 투자판단·투자 권유·추천·유의 같은 조언성 문구를 넣지 마세요. 근거에 그 문장이 있어도 사용자가 요청하지 않은 조언은 답변 범위 밖입니다.",
            "evidence_literal_quotes는 아래 evidence_text의 실제 문자열만 사용하며 chunk_id는 quote가 아닙니다.",
            "user_question_scenario: " + request["user_question_scenario"],
            "supported_requirements: " + json.dumps(request["supported_requirements"], ensure_ascii=False),
            "unsupported_requirements: " + json.dumps(request["unsupported_requirements"], ensure_ascii=False),
            "unsupported_target: " + request["unsupported_target"],
            "required literal evidence quotes: " + json.dumps(request["literal_evidence_quotes"], ensure_ascii=False),
            "evidence_text:\n" + evidence_text,
        ]
    final_banmal_check = banmal_final_question_check_instruction(request)
    if final_banmal_check:
        text.append(final_banmal_check)
    return {
        # The host owns outcome, evidence, completion assembly, and semantic
        # validation.  A modest non-zero value is therefore limited to the
        # model-owned question wording, avoiding deterministic retries that
        # manufacture the same near-duplicate question.
        "messages": [{"role": "user", "content": "\n\n".join(text)}], "temperature": 0.35,
        "maxCompletionTokens": 1400, "thinking": {"effort": "none"},
        "responseFormat": {"type": "json", "schema": schema_for(request)},
    }


def parse_body(body: str) -> dict:
    data = json.loads(body)
    result = data.get("result", {}) if isinstance(data, dict) else {}
    content = result.get("message", {}).get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
    if not isinstance(content, str):
        raise ValueError("missing structured response content")
    if content.strip().startswith("```"):
        content = content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(content)


def hydrate_candidate(
    request: dict,
    model: dict,
    *,
    candidate_id_suffix: str = "",
    generation_attempt: int = 1,
    generation_prompt_version: str = "p49-2h-3d-v4",
    use_model_question: bool = False,
) -> dict:
    lane = request["contract_lane"]
    if lane == "supported_answer":
        requirements, evidence, status = request["requirements"], request["direct_evidence"], "full"
        supported_requirement = request["requirements"][0]["canonical_requirement"]
        rendered = SUPPORTED_HOST_FACTUAL_RENDERERS.get(supported_requirement)
        facts = ([{"text": rendered, "evidence_literal_quotes": request["literal_evidence_quotes"]}]
                 if rendered else model["required_gold_facts"])
    elif lane == "clarification_required":
        requirements, evidence, facts, status = request["requirements"], [], [], "unresolved"
    else:
        requirements = request["supported_requirements"] + request["unsupported_requirements"]
        evidence = request["direct_evidence"]
        supported_rows = request["supported_requirements"]
        if supported_rows:
            status = "partial"
            supported_requirement = supported_rows[0]["canonical_requirement"]
            rendered = BOUNDED_HOST_FACTUAL_RENDERERS.get(supported_requirement)
            if rendered is None:
                raise ValueError(f"bounded host renderer missing for {supported_requirement}")
            facts = [{"text": rendered, "evidence_literal_quotes": request["literal_evidence_quotes"]}]
        else:
            # A bounded/NONE request is valid when the corpus has no direct
            # answer and no supported adjacent fact.  It must never borrow an
            # optional-context chunk merely to make the answer look fuller.
            status, facts = "none", []
    gold_facts = []
    supported_requirement = next((row["canonical_requirement"] for row in requirements if row["support_status"] == "supported" and row["coverage_required"]), None)
    chunk_id = evidence[0]["chunk_id"] if evidence else None
    for index, fact in enumerate(facts, start=1):
        gold_facts.append({
            "fact_id": f"F{index}", "requirement": supported_requirement, "text": fact["text"],
            "evidence_chunk_ids": [chunk_id] if chunk_id else [],
            # Literal quote authority is host-owned.  The model may describe a
            # fact but cannot choose a chunk ID or redefine the quote contract.
            "evidence_literal_quotes": request["literal_evidence_quotes"],
        })
    modifiers = {**model["modifiers"], "evidence_status": status, "contract_lane": lane}
    if lane == "clarification_required":
        modifiers["missing_conditions"] = request["missing_conditions"]
        # The model can help exercise the lane schema, but the actual
        # clarification scope is host-owned.  Rendering the exact missing
        # conditions prevents accidental extra questions and avoids an awkward
        # run-on sentence when more than one condition is needed.
        questions = [f"- {condition}" for condition in request["missing_conditions"]]
        draft_completion = (
            "[답변] 정확히 안내하려면 다음 정보를 알려주세요.\n"
            + "\n".join(questions)
            + "\n[근거] 없음\n[유의사항] 필요한 조건을 확인한 뒤 제공 자료 기준으로 안내할 수 있습니다."
        )
    elif lane == "bounded_answer":
        target = request["unsupported_target"]
        disclosure = f"제공된 자료에는 {target} 정보가 없습니다."
        supported_rows = request["supported_requirements"]
        if supported_rows:
            supported_requirement = supported_rows[0]["canonical_requirement"]
            supported_text = BOUNDED_HOST_FACTUAL_RENDERERS[supported_requirement]
            draft_completion = f"[답변] {supported_text}\n[근거] " + " / ".join(request["literal_evidence_quotes"]) + f"\n[유의사항] {disclosure}"
        else:
            draft_completion = f"[답변] 제공된 자료만으로는 요청하신 내용을 확인할 수 없습니다.\n[근거] 없음\n[유의사항] {disclosure}"
        modifiers["unsupported_target"] = target
        modifiers["unsupported_disclosure"] = disclosure
        modifiers["supported_answer_required_terms"] = request.get("supported_answer_required_terms", [])
    else:
        supported_text = SUPPORTED_HOST_FACTUAL_RENDERERS.get(supported_requirement, model["answer_text"].strip())
        draft_completion = "[답변] " + supported_text + "\n[근거] " + " / ".join(request["literal_evidence_quotes"]) + "\n[유의사항] 없음"
        modifiers["answer_contract"] = request["answer_contract"]
    return {
        "candidate_schema_version": "p49.2h.contract-split.host-completion.v2", "candidate_id": request["micro_request_id"].replace("3C", "AUG-3C") + candidate_id_suffix,
        "micro_request_id": request["micro_request_id"], "source_seed_id": request["source_seed_id"], "question_type": request["question_type"],
        "factual_domain": request["factual_domain"], "coverage_cell": request["coverage_cell"], "target_outcome": lane,
        "outcome": lane, "modifiers": modifiers,
        # Micro records intentionally keep reviewed host wording.  Full
        # augmentation retains the same factual host assembly but must keep
        # the model's controlled question variation to avoid repeated
        # scenarios for one evidence/cell pairing.
        "question": model["question"] if use_model_question else request.get(
            "user_question_scenario",
            SUPPORTED_HOST_QUESTION_RENDERERS.get(supported_requirement, model["question"]),
        ),
        "requirements": requirements, "evidence_status": status, "direct_evidence": evidence, "required_gold_facts": gold_facts,
        "optional_relevant_context": [], "draft_completion": draft_completion, "generation_status": "generated",
        "generation_model": "HCX-007", "generation_prompt_version": generation_prompt_version,
        "generation_attempt": generation_attempt,
        "generation_parameters": {"temperature": 0, "topP": None, "maxTokens": 1400},
        "validation_status": "pending", "validation_failures": [], "human_review_status": "pending",
        "acceptance_status": "not_accepted", "pool_id": request["pool_id"],
        "subject_contract": subject_contract_for_evidence(evidence),
        # This is intentionally descriptive only: automated validation may
        # advance schema/evidence/semantic/dedup observations, but cannot
        # advance human_reviewed or accepted.
        "candidate_lifecycle": {
            "state": "generated", "schema": "pending", "evidence": "pending",
            "semantic": "pending", "dedup": "pending", "human_review": "pending",
            "acceptance": "not_accepted",
        },
    }


def validation_findings_for_attempt(candidate: dict, corpus: dict[str, dict], previous_questions: list[str], seed_questions: list[str]) -> list[str]:
    """Run host validation before deciding whether a bounded retry is warranted."""
    findings = validate(candidate, corpus)
    question = candidate["question"]
    if any(similarity(question, seed) >= 0.88 for seed in seed_questions):
        findings.append("near_duplicate_frozen_seed")
    if any(similarity(question, prior) >= 0.88 for prior in previous_questions):
        findings.append("near_duplicate_candidate")
    return sorted(set(findings))


def select_requests(all_requests: list[dict], completed: set[str], request_ids: str | None, max_requests: int) -> list[dict]:
    """Select an explicit balanced slice without silently changing its lane."""
    remaining = [row for row in all_requests if row["micro_request_id"] not in completed]
    if not request_ids:
        return remaining[:max_requests]
    wanted = [item.strip() for item in request_ids.split(",") if item.strip()]
    found = {row["micro_request_id"]: row for row in remaining}
    unknown = [item for item in wanted if item not in found]
    if unknown:
        raise ValueError("Unknown or already completed micro request IDs: " + ", ".join(unknown))
    if len(wanted) > max_requests:
        raise ValueError("--request-ids exceeds --max-requests")
    return [found[item] for item in wanted]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Required: makes paid external HCX-007 calls.")
    parser.add_argument("--requests", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_requests_v1.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_raw_v4.jsonl")
    parser.add_argument("--max-requests", type=int, default=35)
    parser.add_argument("--request-ids", help="Comma-separated explicit micro_request_id values for a balanced slice.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-generation-attempts", type=int, default=3, help="Bounded host retry limit after validation failures (1..3).")
    parser.add_argument("--candidate-id-suffix", default="", help="Unique suffix for a remediation artifact; never overwrites prior candidate IDs.")
    parser.add_argument("--generation-prompt-version", default="p49-2h-3d-v4", help="Host prompt/contract version recorded in generated provenance.")
    args = parser.parse_args()
    if not args.execute:
        parser.error("The 3C micro-pilot makes external HCX calls. Re-run with --execute after review.")
    if not 1 <= args.max_requests <= 35:
        parser.error("--max-requests must be within 1..35")
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")
    if args.output.exists() and not args.resume:
        parser.error("Output exists. Use --resume or a new output path.")
    load_dotenv(ROOT / ".env")
    settings = GenerationSettings.from_env()
    if settings.generator_backend.lower() != "hcx" or settings.hcx_model.upper() != "HCX-007" or not settings.hcx_api_key or not settings.hcx_base_url:
        raise RuntimeError("Micro-pilot requires configured HCX-007, HCX_API_KEY, and HCX_BASE_URL.")
    settings = replace(settings, hcx_min_interval_seconds=max(settings.hcx_min_interval_seconds, 4.0))
    existing = read_jsonl(args.output) if args.output.exists() else []
    completed = {row.get("micro_request_id") for row in existing}
    requests = select_requests(read_jsonl(args.requests), completed, args.request_ids, args.max_requests)
    previous_questions = [row.get("question", "") for row in existing]
    corpus = {row["chunk_id"]: row for row in read_validation_jsonl(CORPUS)}
    seed_questions = [row["question"] for row in read_validation_jsonl(FROZEN_SEED)]
    generator = HCXStructuredAugmentationGenerator(config=settings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for request in requests:
        attempt_history: list[dict] = []
        retry_findings: list[str] = []
        candidate: dict | None = None
        for attempt in range(1, args.max_generation_attempts + 1):
            payload = build_payload(request, previous_questions, retry_findings)
            model = generator.generate_structured(payload["messages"][0]["content"], payload["responseFormat"]["schema"])
            candidate = hydrate_candidate(
                request, model,
                candidate_id_suffix=args.candidate_id_suffix,
                generation_attempt=attempt,
                generation_prompt_version=args.generation_prompt_version,
            )
            candidate["generation_attempt"] = attempt
            candidate["generation_parameters"] = {
                "temperature": payload["temperature"], "topP": payload.get("topP"),
                "maxTokens": payload["maxCompletionTokens"],
            }
            retry_findings = validation_findings_for_attempt(candidate, corpus, previous_questions, seed_questions)
            attempt_history.append({"attempt": attempt, "validation_findings": retry_findings})
            if not retry_findings:
                break
        assert candidate is not None
        candidate["generation_attempt_history"] = attempt_history
        if retry_findings:
            # The record is retained only as an auditable rejected raw attempt.
            # This is not human review and cannot be exported or accepted.
            candidate["generation_status"] = "generation_exhausted"
            candidate["generation_exhausted"] = True
            candidate["validation_failures"] = retry_findings
        else:
            candidate["generation_exhausted"] = False
        previous_questions.append(candidate["question"])
        with args.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        print(json.dumps({
            "micro_request_id": request["micro_request_id"], "status": candidate["generation_status"],
            "generation_attempt": candidate["generation_attempt"], "findings": retry_findings,
        }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
