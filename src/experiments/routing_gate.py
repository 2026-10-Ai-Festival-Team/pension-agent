"""P10-B/C 실험용 deterministic router와 route-specific gate.

Production PensionAgent에는 연결하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.multi_evidence import RequirementCase, RequirementEvidenceSelector
from src.experiments.query_understanding import RequirementBuilder, SupportClassifier


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reasons: list[str]
    requirement_case: RequirementCase | None = None


class ExperimentalRouter:
    def __init__(self) -> None:
        self.support_classifier = SupportClassifier()
        self.requirement_builder = RequirementBuilder()

    def classify(self, analysis) -> RouteDecision:
        question = analysis.question
        extracted = analysis.extracted_entities
        support = self.support_classifier.classify(question)
        if not support.supported or analysis.intent in {"unsupported_or_personal", "conditional_recommendation"}:
            return RouteDecision("unsupported", [support.category if not support.supported else analysis.intent])
        plan = self.requirement_builder.build(analysis)
        # DB/DC 운용 주체는 두 대상의 값을 확인하지만 하나의 직접 사실을 묻는
        # simple route다. requirement slot은 simple gate에서도 모두 검증한다.
        if plan.category == "shared_operation_comparison":
            return RouteDecision("simple", [f"requirements:{plan.category}"], plan.case)
        if plan.requirement_count >= 2:
            return RouteDecision("compound", [f"requirements:{plan.category}"], plan.case)
        if plan.requirement_count == 1:
            return RouteDecision("simple", [f"requirements:{plan.category}"], plan.case)
        reasons = []
        if extracted.comparison:
            reasons.append("comparison")
        if len(extracted.accounts) >= 2:
            reasons.append("multiple_accounts")
        if "원리금보장" in question and "채권형" in question:
            reasons.append("multiple_requested_topics")
        if "해지" in question and extracted.tax_intent:
            reasons.append("tax_with_conditions")
        return RouteDecision("compound" if reasons else "simple", reasons or ["single_fact"])


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
            fallback_plan = RequirementBuilder().build(analysis)
            requirement_case = requirement_case or (
                fallback_plan.case if fallback_plan.requirement_count else None
            )
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
