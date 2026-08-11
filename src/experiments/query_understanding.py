"""P14 실험용 지원 범위 분류와 requirement-first 질문 구조화."""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.multi_evidence import RequirementCase, RequirementSlot


@dataclass(frozen=True)
class SupportDecision:
    supported: bool
    category: str
    reason: str


class SupportClassifier:
    """문서 기반 답변 범위와 근거 부족을 구분하는 결정적 분류기."""

    def classify(self, question: str) -> SupportDecision:
        normalized = question.replace(" ", "")
        if self._is_personal_account_lookup(normalized):
            return SupportDecision(False, "personal_account_lookup", "personal_account_state_requested")
        if any(marker in normalized for marker in ("오늘기준", "최신", "실시간")):
            return SupportDecision(False, "unavailable_external_information", "time_sensitive_external_information")
        if self._is_unconditional_recommendation(normalized):
            return SupportDecision(False, "unsupported_recommendation_or_prediction", "ranking_or_recommendation_requested")
        return SupportDecision(True, "supported", "document_grounded_question")

    @staticmethod
    def _is_personal_account_lookup(question: str) -> bool:
        possessive = any(marker in question for marker in ("제", "내", "제가", "우리"))
        account_state = any(
            marker in question
            for marker in ("계좌", "적립금", "잔액", "운용수익률", "수익률", "보유상품")
        )
        return possessive and account_state

    @staticmethod
    def _is_unconditional_recommendation(question: str) -> bool:
        product_selection = any(marker in question for marker in ("추천", "골라", "선정", "가장수익"))
        product_context = any(marker in question for marker in ("상품", "펀드", "수익률", "수익"))
        return product_selection and product_context


@dataclass(frozen=True)
class RequirementPlan:
    case: RequirementCase
    category: str

    @property
    def requirement_count(self) -> int:
        return len(self.case.slots)


class RequirementBuilder:
    """질문의 명시 subject·attribute에서 재사용 가능한 evidence slot을 만든다."""

    _PRODUCT_FIELD_TERMS = {
        "product_name": ("상품명", "펀드명"),
        "risk_grade": ("위험등급", "위험 등급"),
        "fee": ("판매수수료", "총보수", "보수ㆍ비용", "보수·비용"),
        "investment_target": ("투자대상", "투자 대상", "투자"),
        "investment_strategy": ("운용전략", "운용 전략", "투자전략", "투자 전략"),
        "effective_date": ("기준일", "작성기준일", "작성 기준일"),
    }

    def build(self, analysis) -> RequirementPlan:
        question = analysis.question
        extracted = analysis.extracted_entities
        product_plan = self._product_plan(analysis)
        if product_plan is not None:
            return product_plan
        if self._has_db_dc_calculation_and_operation(question, extracted.accounts):
            return self._plan("db_dc_calculation_and_operation", (
                RequirementSlot("DB 급여 산정", ("DB", "퇴직급여", "평균임금"), 2, key="db_benefit"),
                RequirementSlot("DC 급여 산정", ("DC", "부담금", "운용"), 2, key="dc_benefit"),
                RequirementSlot("DB 적립금 운용", ("DB", "회사", "운용"), 2, key="db_operation"),
                RequirementSlot("DC 적립금 운용", ("DC", "근로자", "운용"), 2, key="dc_operation"),
            ))
        if self._has_db_dc_conversion(question, extracted.accounts):
            return self._plan("db_dc_conversion", (
                RequirementSlot("DB에서 DC 전환 가능 여부", ("DB", "DC", "전환 가능"), 3, key="conversion_eligibility"),
                RequirementSlot("전환 금액 산정", ("전환", "계산식", "평균임금"), 2, key="conversion_amount"),
            ))
        if "퇴직연금규약" in question and "동의" in question:
            return self._plan("policy_and_consent", (
                RequirementSlot("퇴직연금규약 내용", ("퇴직연금규약", "내용"), 2, key="policy_content"),
                RequirementSlot("근로자대표 동의", ("근로자대표", "동의"), 2, key="representative_consent"),
            ))
        if "중도인출" in question and any(marker in question for marker in ("절차", "준비", "서류")):
            return self._plan("withdrawal_condition_and_procedure", (
                RequirementSlot("중도인출 사유", ("중도인출", "사유"), 2, key="dc_withdrawal_conditions"),
                RequirementSlot("중도인출 절차", ("중도인출", "신청", "서류"), 2, key="withdrawal_procedure"),
            ))
        if "일시금" in question and any(marker in question for marker in ("과세", "세금")):
            return self._plan("annuity_and_lump_sum_tax", (
                RequirementSlot("연금 수령 과세 시점", ("연금", "과세", "수령"), 2, key="annuity_tax_timing"),
                RequirementSlot("일시금 수령 과세", ("일시금", "퇴직소득세"), 2, key="lump_sum_tax_difference"),
            ))
        if "IRP" in extracted.accounts and "연금" in question and "기간" in question and "함께" in question:
            return self._plan("annuity_age_and_duration", (
                RequirementSlot("연금 수령 연령", ("55", "연금"), 2, key="annuity_age"),
                RequirementSlot("최소 수령기간", ("5 년", "연금"), 2, key="annuity_duration"),
            ))
        if len(extracted.accounts) >= 2 and "적립금을 누가 운용" in question:
            return self._plan("shared_operation_comparison", (
                RequirementSlot("DB·DC 적립금 운용 주체", ("DB", "DC", "적립금 운용 주체"), 3, key="operation_owner_comparison"),
            ))
        return self._plan("single_fact", ())

    def _product_plan(self, analysis) -> RequirementPlan | None:
        fields = analysis.extracted_entities.requested_fields
        codes = analysis.product_codes
        if not codes or not fields:
            return None
        slots = []
        for code in codes:
            for field_name in fields:
                terms = (code,) if field_name == "product_name" else (code, *self._PRODUCT_FIELD_TERMS[field_name])
                slots.append(
                    RequirementSlot(
                        name=f"{code} {field_name}",
                        terms=terms,
                        min_matches=1 if field_name == "product_name" else 2,
                        requires_title=field_name == "product_name",
                        key=f"{code}:{field_name}",
                    )
                )
        return self._plan("product_fields", tuple(slots))

    @staticmethod
    def _has_db_dc_calculation_and_operation(question: str, accounts: list[str]) -> bool:
        return {"DB", "DC"} <= set(accounts) and "산정" in question and any(
            marker in question for marker in ("운용", "책임", "굴리")
        )

    @staticmethod
    def _has_db_dc_conversion(question: str, accounts: list[str]) -> bool:
        return {"DB", "DC"} <= set(accounts) and any(marker in question for marker in ("바꿀", "전환")) and any(
            marker in question for marker in ("계산", "산정")
        )

    @staticmethod
    def _plan(category: str, slots: tuple[RequirementSlot, ...]) -> RequirementPlan:
        return RequirementPlan(
            case=RequirementCase(
                question_id=f"dynamic:{category}",
                role="p14_requirement_builder",
                slots=slots,
            ),
            category=category,
        )
