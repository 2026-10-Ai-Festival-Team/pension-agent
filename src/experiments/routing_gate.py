"""P10-B/C 실험용 deterministic router와 route-specific gate.

Production PensionAgent에는 연결하지 않는다.
"""
from dataclasses import dataclass

from src.experiments.multi_evidence import RequirementEvidenceSelector


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
        if any(phrase in question for phrase in ("투자대상과 운용전략", "투자하며 위험등급", "원리금보장 운용방법과 채권형")):
            reasons.append("multiple_required_topics")
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
            if requirement_case is None:
                return RouteGateDecision(False, "compound_requirements_not_defined", [], [])
            selection = self.selector.select(requirement_case, results)
            return RouteGateDecision(
                selection.complete,
                "compound_requirements_complete" if selection.complete else "compound_requirements_incomplete",
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
