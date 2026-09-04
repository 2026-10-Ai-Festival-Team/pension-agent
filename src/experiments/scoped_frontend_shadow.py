"""Read-only preparation shadow for the frozen resolver-first front end."""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.direct_requirement_selector import DIRECT_REQUIREMENT_LABELS
from src.models.document import AuthorityLevel, SourceType
from src.orchestration.context_builder import ContextBuilder


_RETRIEVAL_TERMS = {
    "DB.operation_party": "DB형 적립금 운용 주체 사용자",
    "DC.operation_party": "DC형 적립금 운용 주체 근로자",
    "DB.benefit_determination": "DB형 퇴직급여 평균임금 계속근로기간",
    "DC.benefit_determination": "DC형 퇴직급여 사용자 부담금 운용성과",
    "DC.employer_contribution": "DC형 사용자 부담금 연간 임금총액 12분의1",
    "retirement_pension.participant_education.frequency": "퇴직연금 가입자 교육 매년 1회",
    "retirement_pension.participant_education.outsourcing": "퇴직연금 가입자 교육 위탁 가능",
    "DC.early_withdrawal.allowed_reasons": "DC형 중도인출 법정사유",
    "DC.early_withdrawal.required_documents": "DC형 중도인출 증빙서류",
    "pension_savings.early_withdrawal.allowed_reasons": "연금저축 중도인출 부득이한 사유",
    "pension_savings.withdrawal.tax_treatment": "연금저축 중도인출 기타소득세 부득이한 사유",
    "IRP.early_withdrawal.allowed_reasons": "IRP 중도인출 근퇴법 법으로 열거 주택 구입 전세보증금 요양 개인회생 파산",
    "IRP.withdrawal.tax_treatment": "연금계좌 IRP 연금저축 중도인출 기타소득세 부득이한 사유",
    "ISA.transfer.deadline": "ISA 만기 연금계좌 이전 60일 기한",
    "ISA.transfer.additional_tax_credit": "ISA 만기 연금계좌 이전 추가 세액공제 10% 300만원",
    "retirement_pension.in_kind_transfer.IRP.application_route": "IRP 실물이전 신청 경로",
    "retirement_income.IRP_transfer.tax_timing": "퇴직소득 IRP 이체 연금수령 과세",
    "product.risk_grade.current": "펀드 투자 위험 등급 분류 1등급 2등급",
    "product.risk_grade.change_possibility": "펀드 위험 등급 운용실적 시장 상황 변경될 수",
    "product.risk_grade.historical": "위험등급 변경내역 과거",
    "product.tracking_index": "추종 기준지수 비교지수",
    "product.equity_allocation_limit": "주식 편입 비중 최대",
    "product.total_fee": "총보수 지급비율 연간",
    "product.period_cost": "1,000만원 투자기간별 총비용 예시",
}

_PRODUCT_ANCHOR_FIELDS = {
    "product.risk_grade.current": "risk_grade",
    "product.risk_grade.change_possibility": "risk_grade_changeability",
}

# Canonical-requirement signals identify the direct factual field.  They are
# intentionally independent of P42 IDs and specific document/chunk IDs.
_DIRECT_FIELD_SIGNALS = {
    "ISA.transfer.additional_tax_credit": {
        # A summary table can contain the cap without the conversion-rate
        # rule.  The direct long-form source states both, so do not let the
        # former satisfy a request for the rate *and* cap.
        "required_all": ("ISA", "10%", "300만원"),
        "required_any": (),
        "forbidden_any": (),
    },
    "product.total_fee": {
        "required_all": ("지급비율", "연간", "총 보수"),
        "required_any": (),
        "forbidden_any": ("투자기간", "1,000만원 투자"),
    },
    "retirement_income.IRP_transfer.tax_timing": {
        "required_all": ("연금수령", "과세"),
        "required_any": ("퇴직소득", "이연퇴직소득", "과세이연", "인출 전"),
        "forbidden_any": (),
    },
    "IRP.early_withdrawal.allowed_reasons": {
        # A list of examples alone does not establish the legal boundary of
        # this field.  Bind the primary text that says IRP withdrawal grounds
        # are enumerated by law, alongside the allowed-reasons table.
        "required_all": ("IRP", "중도인출"),
        "required_any": ("중도인출 사유를 법으로 열거", "근퇴법 적용"),
        "forbidden_any": (),
    },
}


@dataclass(frozen=True)
class ScopedFrontendShadowPlan:
    status: str
    active_subject: str | None
    selected_requirements: tuple[str, ...]
    requirement_candidates: dict[str, tuple[str, ...]]
    contexts: tuple
    reason: str | None


class ScopedFrontendPreparationShadow:
    """Retrieve per frozen requirement without modifying any candidate path.

    The class deliberately does not call HCX, run the Evidence Gate, or produce
    an answer.  It is a context-divergence instrument for the shadow phase.
    """

    def __init__(self, retriever, context_builder=None, *, per_requirement_top_k: int = 2, max_contexts: int = 5):
        self.retriever = retriever
        self.context_builder = context_builder or ContextBuilder()
        self.per_requirement_top_k = per_requirement_top_k
        self.max_contexts = max_contexts

    @staticmethod
    def retrieval_query(active_subject: str, requirement: str) -> str:
        """Build a query from resolved scope and canonical fact only.

        Do not append the raw question here.  A raw ordinal/comparison question
        can retain entities explicitly excluded by the resolver and re-open a
        product/account scope that has already been decided upstream.
        """
        subject = active_subject.removeprefix("product:")
        terms = _RETRIEVAL_TERMS.get(requirement, DIRECT_REQUIREMENT_LABELS[requirement])
        return f"{subject} {terms}"

    @staticmethod
    def _is_direct_field_evidence(result, requirement: str) -> bool:
        signals = _DIRECT_FIELD_SIGNALS.get(requirement)
        if signals is None:
            return True
        if result.source_type != SourceType.ORIGINAL or result.authority_level != AuthorityLevel.PRIMARY:
            return False
        text = " ".join((result.title or "", result.section or "", result.text)).casefold()
        normalized = " ".join(text.split())
        if any(term.casefold() in normalized for term in signals["forbidden_any"]):
            return False
        if not all(term.casefold() in normalized for term in signals["required_all"]):
            return False
        required_any = signals["required_any"]
        return not required_any or any(term.casefold() in normalized for term in required_any)

    def _resolved_scope_results(self, active_subject: str, requirement: str, query: str) -> tuple:
        """Return candidates which preserve an already resolved product scope.

        Product codes live in corpus metadata, so putting a code into a BM25
        query is not a sufficient scope constraint.  This keeps only BM25
        results tagged with the resolved code and adds the frozen retriever's
        direct product-field anchors where they exist.  It neither changes
        BM25 nor lets a raw-question entity re-enter the search scope.
        """
        product_code = active_subject.removeprefix("product:") if active_subject.startswith("product:") else None
        needs_direct_field = requirement in _DIRECT_FIELD_SIGNALS
        search_top_k = max(self.per_requirement_top_k, 25) if product_code or needs_direct_field else self.per_requirement_top_k
        bm25_results = tuple(self.retriever.search(query, top_k=search_top_k).results)
        if not product_code:
            if needs_direct_field:
                return tuple(
                    result for result in bm25_results
                    if self._is_direct_field_evidence(result, requirement)
                )[:self.per_requirement_top_k]
            return bm25_results[:self.per_requirement_top_k]

        code = product_code.upper()
        scoped_bm25 = [
            result for result in bm25_results
            if code in {item.upper() for item in result.product_codes}
        ]
        anchors = []
        anchor_field = _PRODUCT_ANCHOR_FIELDS.get(requirement)
        anchor_lookup = getattr(self.retriever, "product_field_anchors", None)
        if anchor_field and callable(anchor_lookup):
            anchors.extend(anchor_lookup(product_code, anchor_field, top_k=self.per_requirement_top_k))

        selected, seen = [], set()
        direct_bm25 = [
            result for result in scoped_bm25
            if self._is_direct_field_evidence(result, requirement)
        ]
        # If a canonical requirement demands direct evidence, indirect chunks
        # cannot become sufficient merely because their product scope matches.
        ranked_bm25 = direct_bm25 if needs_direct_field else scoped_bm25
        for result in (*anchors, *ranked_bm25):
            if result.chunk_id not in seen:
                selected.append(result)
                seen.add(result.chunk_id)
            if len(selected) == self.per_requirement_top_k:
                break
        return tuple(selected)

    def prepare(self, question: str, frozen_frontend: dict) -> ScopedFrontendShadowPlan:
        status = frozen_frontend["status"]
        if status == "unresolved_scope":
            return ScopedFrontendShadowPlan("unresolved_scope", None, (), {}, (), frozen_frontend.get("reason"))
        if status != "selected":
            return ScopedFrontendShadowPlan("frontend_contract_error", None, (), {}, (), f"unexpected_status:{status}")
        active = frozen_frontend.get("active_subject")
        requirements = tuple(frozen_frontend.get("selected_requirements", ()))
        allowed = set(frozen_frontend.get("allowed_requirements", ()))
        if not active or not requirements or not set(requirements) <= allowed:
            return ScopedFrontendShadowPlan("frontend_contract_error", active, requirements, {}, (), "invalid_frozen_frontend_contract")
        candidates, requirement_candidates = [], {}
        for requirement in requirements:
            label = DIRECT_REQUIREMENT_LABELS.get(requirement)
            if label is None:
                return ScopedFrontendShadowPlan("frontend_contract_error", active, requirements, requirement_candidates, (), f"unknown_requirement:{requirement}")
            query = self.retrieval_query(active, requirement)
            results = self._resolved_scope_results(active, requirement, query)
            requirement_candidates[requirement] = tuple(item.chunk_id for item in results)
            candidates.extend(results)
        contexts = tuple(self.context_builder.build(candidates, self.max_contexts))
        return ScopedFrontendShadowPlan("prepared", active, requirements, requirement_candidates, contexts, None)
