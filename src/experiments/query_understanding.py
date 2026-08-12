"""P14 실험용 지원 범위 분류와 requirement-first 질문 구조화."""
from __future__ import annotations

from dataclasses import dataclass
import re

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
        if self._is_personal_account_lookup(question):
            return SupportDecision(False, "personal_account_lookup", "personal_account_state_requested")
        if any(marker in normalized for marker in ("오늘기준", "최신", "실시간")):
            return SupportDecision(False, "unavailable_external_information", "time_sensitive_external_information")
        if self._is_external_prediction(normalized):
            return SupportDecision(False, "unsupported_recommendation_or_prediction", "external_prediction_requested")
        if self._is_unconditional_recommendation(normalized):
            return SupportDecision(False, "unsupported_recommendation_or_prediction", "ranking_or_recommendation_requested")
        return SupportDecision(True, "supported", "document_grounded_question")

    @staticmethod
    def _is_personal_account_lookup(question: str) -> bool:
        """한국어 조사 경계를 보존해 제도·공제의 ``제`` 오탐을 막는다."""
        possessive = bool(
            re.search(r"(?:^|[\s,])제(?:[\s]|$)", question)
            or re.search(r"제가(?:[\s]|$)", question)
            or re.search(r"(?:^|[\s,])내(?:[\s]|$)", question)
            or re.search(r"(?:^|[\s,])우리(?:[\s]|$)", question)
        )
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

    @staticmethod
    def _is_external_prediction(question: str) -> bool:
        future = any(marker in question for marker in ("내일", "다음달", "다음 달", "향후"))
        prediction = any(marker in question for marker in ("전망", "예측", "금리", "수익률"))
        return future and prediction


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
        "investment_target": ("투자대상", "투자 대상"),
        "investment_strategy": ("운용전략", "운용 전략", "투자전략", "투자 전략"),
        "effective_date": ("기준일", "작성기준일", "작성 기준일"),
    }
    _PRODUCT_FIELD_EVIDENCE_TERMS = {
        "investment_target": ("투자비율", "주된 투자대상", "주로 투자", "이상 투자"),
        "investment_strategy": ("투자합니다", "운용합니다", "투자 비중", "운용전략"),
        "effective_date": ("작성기준일", "기준일 :", "기준일:"),
    }

    def build(self, analysis) -> RequirementPlan:
        question = analysis.question
        extracted = analysis.extracted_entities
        product_plan = self._product_plan(analysis)
        if product_plan is not None:
            return product_plan
        if self._has_db_dc_benefit_calculation(question, extracted.accounts):
            slots = [
                RequirementSlot("DB 급여 산정", ("DB", "퇴직급여", "평균임금"), 2, key="db_benefit"),
                RequirementSlot("DC 급여 산정", ("DC", "부담금", "운용"), 2, key="dc_benefit"),
            ]
            if self._has_operation_request(question):
                slots.extend(self._db_dc_operation_slots())
            return self._plan("db_dc_benefit_calculation", tuple(slots))
        if self._has_db_dc_conversion(question, extracted.accounts):
            slots = [
                RequirementSlot("DB에서 DC 전환 가능 여부", ("DB", "DC", "전환 가능"), 3, key="conversion_eligibility"),
                RequirementSlot("전환 금액 산정", ("전환", "계산식", "평균임금"), 2, key="conversion_amount"),
            ]
            if not any(marker in question for marker in ("계산", "산정")):
                slots[1] = RequirementSlot("제도전환 규약·동의 조건", ("퇴직연금규약", "동의"), 2, key="conversion_conditions")
            return self._plan("db_dc_conversion", tuple(slots))
        if self._has_severance_pension_comparison(question):
            return self._plan("severance_and_pension_comparison", (
                RequirementSlot("퇴직금 지급 방식", ("퇴직금", "사용자", "지급"), 2, key="severance_payment"),
                RequirementSlot("퇴직연금 적립·지급 방식", ("퇴직연금", "금융기관", "적립"), 2, key="pension_accumulation"),
            ))
        if self._has_principal_bond_classification(question):
            return self._plan("principal_and_bond_classification", (
                RequirementSlot("원리금보장 운용방법 분류", ("원리금보장", "운용방법"), 2, key="principal_guaranteed_class"),
                RequirementSlot("채권형 펀드 분류", ("채권형", "펀드"), 2, key="bond_fund_class"),
            ))
        if self._has_account_cancellation_tax(question):
            return self._plan("account_cancellation_tax", (
                RequirementSlot("해지 가산세", ("해지", "가산세"), 2, key="cancellation_penalty_tax"),
                RequirementSlot("연금외수령 과세", ("연금외수령", "과세"), 2, key="non_annuity_tax"),
                RequirementSlot("해지 과세 예외", ("해지", "부득이한 사유"), 2, key="cancellation_exception"),
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
        if self._has_dc_withdrawal_condition(question, extracted.accounts):
            return self._plan("dc_withdrawal_conditions", (
                RequirementSlot(
                    "DC 중도인출의 계정별 법정사유·요건",
                    ("DC 에서 중도인출", "무주택", "요양", "파산"),
                    2,
                    max_term_span=100,
                    key="dc_withdrawal_conditions",
                ),
            ))
        if "일시금" in question and any(marker in question for marker in ("과세", "세금")):
            return self._plan("annuity_and_lump_sum_tax", (
                RequirementSlot("연금 수령 과세 시점", ("연금", "과세", "수령"), 2, key="annuity_tax_timing"),
                RequirementSlot("일시금 수령 과세", ("일시금", "퇴직소득세"), 2, key="lump_sum_tax_difference"),
            ))
        if self._has_irp_annuity_age_and_duration(question, extracted.accounts):
            return self._plan("annuity_age_and_duration", (
                RequirementSlot(
                    "연금 수령 연령",
                    ("IRP", "55 세"),
                    2,
                    key="annuity_age",
                    retrieval_query="개인형퇴직연금 연금 지급기간 5년 이상",
                ),
                RequirementSlot(
                    "최소 수령기간",
                    ("IRP", "5 년", "연금"),
                    3,
                    key="annuity_duration",
                    retrieval_query="개인형퇴직연금 연금 지급기간 5년 이상",
                ),
            ))
        if len(extracted.accounts) >= 2 and self._has_operation_request(question):
            return self._plan("shared_operation_comparison", tuple(self._db_dc_operation_slots()))
        if self._has_implicit_operation_contrast(question):
            return self._plan("implicit_operation_contrast", tuple(self._db_dc_operation_slots()))
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
                        retrieval_query=f"{code} {' '.join(self._PRODUCT_FIELD_TERMS.get(field_name, ())) }".strip(),
                        reject_table_of_contents=True,
                        required_any_text_terms=self._PRODUCT_FIELD_EVIDENCE_TERMS.get(field_name, ()),
                        forbidden_text_terms=("투자대상이 되는 자산가치",) if field_name == "investment_target" else (),
                        required_text_pattern=r"[1-6]\s*등급" if field_name == "risk_grade" else None,
                    )
                )
        return self._plan("product_fields", tuple(slots))

    @staticmethod
    def _has_db_dc_benefit_calculation(question: str, accounts: list[str]) -> bool:
        return {"DB", "DC"} <= set(accounts) and any(
            marker in question for marker in ("퇴직급여", "급여 산정", "산정 방식", "계산 방식", "결정 방식")
        )

    @staticmethod
    def _has_db_dc_conversion(question: str, accounts: list[str]) -> bool:
        return {"DB", "DC"} <= set(accounts) and any(marker in question for marker in ("바꿀", "바꾸", "전환"))

    @staticmethod
    def _has_severance_pension_comparison(question: str) -> bool:
        return "퇴직금" in question and "퇴직연금" in question and any(
            marker in question for marker in ("차이", "비교", "어떻게 다른")
        )

    @staticmethod
    def _has_principal_bond_classification(question: str) -> bool:
        return "원리금보장" in question and "채권형" in question and any(
            marker in question for marker in ("분류", "소개", "구분")
        )

    @staticmethod
    def _has_account_cancellation_tax(question: str) -> bool:
        return "연금계좌" in question and "해지" in question and any(
            marker in question for marker in ("세금", "과세", "불이익")
        )

    @staticmethod
    def _has_dc_withdrawal_condition(question: str, accounts: list[str]) -> bool:
        return "DC" in accounts and "중도인출" in question and any(
            marker in question for marker in ("조건", "사유", "요건")
        )

    @staticmethod
    def _has_operation_request(question: str) -> bool:
        return any(marker in question for marker in ("운용", "운영", "굴리", "누가 운용", "운용 주체", "책임"))

    @staticmethod
    def _has_implicit_operation_contrast(question: str) -> bool:
        return "퇴직연금" in question and "차이" in question and "회사" in question and any(
            marker in question for marker in ("직접", "내가", "근로자")
        ) and any(marker in question for marker in ("굴리", "운용"))

    @staticmethod
    def _db_dc_operation_slots() -> list[RequirementSlot]:
        return [
            RequirementSlot("DB 적립금 운용", ("DB", "회사", "적립금 운용"), 3, max_term_span=400, key="db_operation"),
            RequirementSlot("DC 적립금 운용", ("DC", "근로자", "적립금 운용"), 3, max_term_span=400, key="dc_operation"),
        ]

    @staticmethod
    def _has_irp_annuity_age_and_duration(question: str, accounts: list[str]) -> bool:
        has_annuity = "연금" in question and any(marker in question for marker in ("수령", "지급", "받"))
        has_age = any(marker in question for marker in ("연령", "나이", "몇 살", "55세", "55 세"))
        has_duration = any(marker in question for marker in ("기간", "몇 년", "몇년", "5년", "5 년"))
        return "IRP" in accounts and has_annuity and has_age and has_duration

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
