"""P10-B/C 실험용 deterministic router와 route-specific gate.

Production PensionAgent에는 연결하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.multi_evidence import RequirementCase, RequirementEvidenceSelector, RequirementSlot


_PRODUCT_FIELD_TERMS = {
    "product_name": ("상품명", "펀드명"),
    "risk_grade": ("위험등급", "위험 등급"),
    "fee": ("판매수수료", "총보수", "보수ㆍ비용", "보수·비용"),
    "investment_target": ("투자대상", "투자 대상", "투자"),
    "investment_strategy": ("운용전략", "운용 전략", "투자전략", "투자 전략"),
    "effective_date": ("기준일", "작성기준일", "작성 기준일"),
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reasons: list[str]


class ExperimentalRouter:
    def classify(self, analysis) -> RouteDecision:
        question = analysis.question
        extracted = analysis.extracted_entities
        if analysis.intent in {"unsupported_or_personal", "conditional_recommendation"}:
            return RouteDecision("unsupported", [analysis.intent])
        if "적립금을 누가 운용" in question:
            return RouteDecision("simple", ["shared_operation_axis"])
        reasons = []
        if extracted.comparison:
            reasons.append("comparison")
        if len(extracted.accounts) >= 2:
            reasons.append("multiple_accounts")
        if len(extracted.requested_fields) >= 2 and not self._has_shared_location_request(question):
            reasons.append("multiple_requested_fields")
        if "원리금보장" in question and "채권형" in question:
            reasons.append("multiple_requested_topics")
        if "해지" in question and extracted.tax_intent:
            reasons.append("tax_with_conditions")
        return RouteDecision("compound" if reasons else "simple", reasons or ["single_fact"])

    @staticmethod
    def _has_shared_location_request(question: str) -> bool:
        """여러 항목의 값이 아니라 공통 확인 위치 하나를 묻는 질문을 보존한다."""
        return any(marker in question for marker in ("어디에 표시", "어디에서 확인", "어디서 확인"))


@dataclass(frozen=True)
class RouteGateDecision:
    sufficient: bool
    reason: str
    missing_slots: list[str]
    selected_chunk_ids: list[str]


class ExperimentalRouteGate:
    def __init__(self) -> None:
        self.selector = RequirementEvidenceSelector()

    def assess(self, route, analysis, results, requirement_case=None) -> RouteGateDecision:
        if route == "unsupported":
            return RouteGateDecision(False, "unsupported_or_personal_or_conditional", [], [])
        if route == "compound":
            requirement_case = requirement_case or self._product_field_case(analysis)
            if requirement_case is None:
                return RouteGateDecision(False, "compound_requirements_not_defined", [], [])
            selection = self.selector.select(requirement_case, results)
            return RouteGateDecision(
                selection.complete,
                "compound_requirements_complete" if selection.complete else "compound_requirements_incomplete",
                selection.missing_slot_names,
                [item.chunk_id for item in selection.contexts],
            )
        if requirement_case is not None:
            selection = self.selector.select(requirement_case, results)
            return RouteGateDecision(
                selection.complete,
                "simple_requirements_complete" if selection.complete else "simple_requirements_incomplete",
                selection.missing_slot_names,
                [item.chunk_id for item in selection.contexts],
            )
        if not results:
            return RouteGateDecision(False, "simple_no_evidence", [], [])
        if analysis.product_codes and not all(
            any(code in item.product_codes or code in item.text.upper() for item in results)
            for code in analysis.product_codes
        ):
            return RouteGateDecision(False, "simple_product_code_evidence_missing", analysis.product_codes, [])
        return RouteGateDecision(True, "simple_evidence_present", [], [results[0].chunk_id])

    @staticmethod
    def _product_field_case(analysis) -> RequirementCase | None:
        """복수 상품 속성 질의를 코드·속성 단위의 일반 evidence slot으로 변환한다."""
        if not analysis.product_codes or len(analysis.extracted_entities.requested_fields) < 2:
            return None
        product_code = analysis.product_codes[0]
        slots = tuple(
            RequirementSlot(
                name=f"{product_code} {field_name}",
                terms=(product_code,) if field_name == "product_name" else (product_code, *_PRODUCT_FIELD_TERMS[field_name]),
                min_matches=1 if field_name == "product_name" else 2,
                requires_title=field_name == "product_name",
            )
            for field_name in analysis.extracted_entities.requested_fields
        )
        return RequirementCase(
            question_id="dynamic_product_fields",
            role="dynamic_product_field_template",
            slots=slots,
        )
