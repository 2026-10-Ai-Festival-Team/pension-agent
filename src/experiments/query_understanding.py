"""P14 실험용 지원 범위 분류와 requirement-first 질문 구조화."""
from __future__ import annotations

from dataclasses import dataclass
import re

from src.experiments.multi_evidence import RequirementCase, RequirementSlot
from src.orchestration.question_normalizer import normalize_pension_question


@dataclass(frozen=True)
class SupportDecision:
    supported: bool
    category: str
    reason: str


class SupportClassifier:
    """문서 기반 답변 범위와 근거 부족을 구분하는 결정적 분류기."""

    def classify(self, question: str) -> SupportDecision:
        normalized = question.replace(" ", "")
        if self._is_prompt_injection(normalized):
            return SupportDecision(False, "prompt_injection", "internal_instruction_or_ungrounded_answer_requested")
        if self._is_personal_account_lookup(question):
            return SupportDecision(False, "personal_account_lookup", "personal_account_state_requested")
        if any(marker in normalized for marker in ("오늘기준", "최신", "실시간")):
            return SupportDecision(False, "unavailable_external_information", "time_sensitive_external_information")
        if self._is_past_performance_safety_premise(question):
            return SupportDecision(True, "safety_premise", "document_grounded_past_performance_premise")
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
        # ``두 상품 중 위험등급이 낮은 쪽을 골라`` is an objective
        # document-field comparison, not a suitability recommendation.  Keep
        # this guard structural: it requires multiple explicit product codes
        # and a factual comparison field, so ordinary “상품 골라 주세요”
        # requests still go to the clarify policy.
        explicit_products = len(set(re.findall(r"KR[A-Z0-9]{10}", question, re.I))) >= 2
        factual_field = any(marker in question for marker in (
            "위험등급", "위험 등급", "투자위험", "총보수", "총 보수",
            "비용", "수익률", "투자대상", "운용전략", "지수",
        ))
        if explicit_products and factual_field:
            return False
        product_selection = any(marker in question for marker in ("추천", "골라", "선정", "가장수익"))
        product_context = any(marker in question for marker in ("상품", "펀드", "수익률", "수익"))
        return product_selection and product_context

    @staticmethod
    def _is_external_prediction(question: str) -> bool:
        future = any(marker in question for marker in ("내일", "다음달", "다음 달", "향후", "연말", "올해말", "년말"))
        prediction = any(marker in question for marker in ("전망", "예측", "금리", "수익률", "코스피", "가장오를", "오를"))
        return future and prediction

    @staticmethod
    def _is_prompt_injection(normalized_question: str) -> bool:
        ignore_instruction = any(
            marker in normalized_question
            for marker in ("이전지시", "지시를무시", "규칙은무시", "출처규칙은무시")
        )
        internal_disclosure = any(
            marker in normalized_question
            for marker in ("내부프롬프트", "시스템프롬프트", "내부지시", "숨은지시")
        )
        return ignore_instruction or internal_disclosure

    @staticmethod
    def _is_past_performance_safety_premise(question: str) -> bool:
        past_performance = any(marker in question for marker in ("과거 수익률", "과거 성과", "과거 실적", "투자실적", "지난 수익률", "지난 성과")) or (
            "지난" in question and any(marker in question for marker in ("수익률", "성과", "실적"))
        )
        return past_performance and any(
            marker in question for marker in ("앞으로", "장래", "계속", "보장", "좋은 선택")
        )


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
        "risk_grade_changeability": ("위험등급 변경", "위험 등급 변경", "등급 변경", "변경될 수", "고정"),
        "total_fee": ("총보수", "총 보수", "총보수ㆍ비용", "총보수·비용"),
        "other_expenses": ("기타비용", "기타 비용"),
        "example_cost": ("1,000만원 투자시", "1,000만원 투자 시", "총비용 예시"),
        "investment_target": ("투자대상", "투자 대상"),
        "investment_strategy": (
            "운용전략", "운용 전략", "투자전략", "투자 전략",
            "투자하는 전략", "어느 정도 투자", "얼마나 투자",
        ),
        "asset_type": ("자산유형", "자산 유형", "펀드유형", "펀드 유형", "주식형", "채권형", "혼합형"),
        "investment_risk": ("투자위험", "투자 위험", "원본손실", "원금손실"),
        "principal_loss_possible": (
            "원본손실", "원금손실", "원금 손실", "원금의 손실",
            "투자원금의 손실", "손실 발생", "손실이 발생",
        ),
        "principal_guarantee_status": ("원금보장", "원금 보장", "원리금보장", "원리금 보장", "보장하지"),
        "effective_date": ("기준일", "작성기준일", "작성 기준일"),
    }
    _PRODUCT_FIELD_RETRIEVAL_TERMS = {
        # 상품 설명서에는 ``위험등급``보다 ``투자 위험 등급`` 및 실제
        # 수익률 변동성 문구가 더 안정적으로 함께 나타난다. 이는 검색어
        # 확장용이며, 아래 slot matcher의 충족 기준은 별도로 유지한다.
        "risk_grade": ("위험등급", "위험 등급", "실제 수익률 변동성"),
        "risk_grade_changeability": (
            "위험등급 변경", "위험 등급 변경", "등급 변경", "변경될 수",
            "운용실적", "시장 상황",
        ),
        "total_fee": ("총보수", "총 보수", "총보수 비용"),
        "other_expenses": ("기타비용", "기타 비용"),
        "example_cost": ("1,000만원 투자시", "1,000만원 투자 시", "총비용 예시"),
        "investment_risk": ("주요 투자 위험", "투자위험", "원본손실", "원금손실"),
        "investment_target": ("투자대상", "주된 투자대상", "투자비율", "60% 이상"),
        "asset_type": ("자산유형", "자산 유형", "주식형", "채권형", "혼합형"),
        "principal_loss_possible": (
            "원본손실", "원금손실", "원금 손실", "투자원금의 손실",
            "원금 보장하지", "손실이 발생",
        ),
        "principal_guarantee_status": ("원금보장", "원리금보장", "보장하지"),
    }
    _PRODUCT_FIELD_EVIDENCE_TERMS = {
        "investment_target": ("투자비율", "주된 투자대상", "주로 투자", "이상 투자"),
        # A historical grade-change table alone does not support a claim that
        # the *future* grade can change.  That requires the direct conditional
        # statement used by this field.
        "risk_grade_changeability": ("변경될 수", "변경될 가능성", "시장 상황"),
        "investment_strategy": (
            "투자합니다", "운용합니다", "투자 비중", "운용전략",
            "운용전환", "전환 후", "채권 중심", "수익률에 연동",
            "지수의 수익률", "지수를 추종",
        ),
        "asset_type": ("자산유형", "자산 유형", "주식형", "채권형", "혼합형"),
        "effective_date": ("작성기준일", "기준일 :", "기준일:"),
        "total_fee": ("총보수", "총 보수"),
        "other_expenses": ("기타비용", "기타 비용"),
        "example_cost": ("1,000만원 투자시", "1,000만원 투자 시", "총비용 예시"),
        "investment_risk": ("원본손실", "원금손실", "투자위험의 주요내용", "투자 위험의 주요내용"),
        "principal_loss_possible": (
            "원본손실", "원금손실", "원금 손실", "원금의 손실",
            "투자원금의 손실", "손실 발생", "손실이 발생",
        ),
        "principal_guarantee_status": ("원금보장", "원리금보장", "보장하지"),
    }

    def build(self, analysis) -> RequirementPlan:
        question = self._canonical_question(analysis.question)
        extracted = analysis.extracted_entities
        product_plan = self._product_plan(analysis)
        if product_plan is not None:
            return product_plan
        if self._has_participant_education(question, extracted.accounts):
            return self._plan("participant_education", (
                RequirementSlot(
                    "가입자 교육 실시 주체",
                    ("사용자", "가입자", "교육"),
                    2,
                    key="education_provider",
                    retrieval_query="퇴직연금 가입자 교육 사용자 실시",
                ),
                RequirementSlot(
                    "가입자 교육 최소 실시 주기",
                    ("매년", "1 회", "교육"),
                    2,
                    key="education_frequency",
                    retrieval_query="퇴직연금 가입자 교육 매년 1회 이상",
                    required_any_text_terms=("매년", "1 회", "1회"),
                ),
                RequirementSlot(
                    "가입자 교육 위탁 가능 여부",
                    ("위탁", "퇴직연금사업자", "전문기관"),
                    2,
                    key="education_outsourcing",
                    retrieval_query="퇴직연금 가입자 교육 위탁 퇴직연금사업자 전문기관",
                    required_any_text_terms=("위탁",),
                ),
            ))
        if self._has_in_kind_transfer_request(question, extracted.accounts):
            return self._plan("in_kind_transfer_application", (
                RequirementSlot(
                    "실물이전 의미",
                    ("실물이전", "매도", "금융회사"),
                    2,
                    key="in_kind_transfer_meaning",
                    retrieval_query="퇴직연금 실물이전 상품 매도 없이 금융회사 변경",
                ),
                RequirementSlot(
                    "DB·DC 실물이전 신청 경로",
                    ("DB", "DC", "회사", "신청"),
                    3,
                    key="db_dc_in_kind_transfer_application",
                    retrieval_query="DB DC 실물이전 재직 중 회사 신청",
                ),
                RequirementSlot(
                    "IRP 실물이전 신청 경로",
                    ("IRP", "영업점", "모바일"),
                    2,
                    key="irp_in_kind_transfer_application",
                    retrieval_query="IRP 실물이전 영업점 모바일 신청",
                ),
            ))
        if self._has_retirement_etf_restriction(question, extracted.accounts):
            return self._plan("retirement_etf_restriction", (
                RequirementSlot(
                    "DC·IRP ETF 직접매매 범위",
                    ("DC", "IRP", "ETF", "직접"),
                    3,
                    key="retirement_etf_direct_trade",
                    retrieval_query="DC IRP ETF 직접 매매 가능",
                ),
                RequirementSlot(
                    "레버리지·인버스 ETF 제한",
                    ("레버리지", "인버스", "금지"),
                    2,
                    key="retirement_etf_leverage_inverse_restriction",
                    retrieval_query="DC IRP 레버리지 인버스 ETF 금지",
                ),
            ))
        if self._has_isa_maturity_transfer(question, extracted.accounts):
            slots = []
            if any(marker in question for marker in ("기한", "언제까지", "60일", "60 일")):
                slots.append(RequirementSlot(
                    "ISA 만기자금 이전 기한",
                    ("ISA", "60일", "전환납입"),
                    2,
                    key="isa_transfer_deadline",
                    retrieval_query="ISA 만기 자금 60일 연금계좌 전환납입",
                    required_any_text_terms=("60일", "60 일"),
                ))
            slots.append(RequirementSlot(
                "ISA 이전 추가 세액공제 기준·한도",
                ("ISA전환입금", "10%", "300"),
                2,
                key="isa_transfer_additional_tax_credit",
                retrieval_query="ISA전환입금 10% 300만원 세액공제",
                required_any_text_terms=("10%", "10 %", "300"),
                # A flowchart that mentions only the maximum does not
                # establish the requested calculation basis.  Keep the
                # percentage and cap in the evidence body together.
                required_body_all_text_terms=("300",),
                required_body_any_text_terms=("10%", "10 %"),
            ))
            if self._has_isa_transfer_tax_timing_request(question):
                slots.append(RequirementSlot(
                    "ISA 전환금 인출·과세 처리",
                    ("ISA전환금", "비과세", "인출"),
                    2,
                    key="isa_transfer_tax_timing",
                    retrieval_query="세액공제를 받지 않은 납입금 ISA전환금 포함 인출 전액 비과세",
                    required_body_all_text_terms=("ISA전환금", "비과세"),
                ))
            return self._plan("isa_maturity_transfer", tuple(slots))
        if self._has_irp_eligibility_request(question, extracted.accounts):
            return self._plan("irp_eligibility", (
                RequirementSlot(
                    "IRP 가입 가능 대상",
                    ("IRP", "가입", "퇴직급여"),
                    2,
                    key="irp_eligibility",
                    retrieval_query="개인형퇴직연금 IRP 가입대상 퇴직급여 일시금 DB DC 자영업자",
                    required_any_text_terms=("퇴직급여", "DB", "DC", "자영업자", "근로자"),
                    required_body_any_text_terms=("퇴직급여", "DB", "DC", "자영업자", "근로자"),
                ),
            ))
        if self._has_foreign_etf_account_tax_comparison(question, extracted.accounts):
            return self._plan("foreign_etf_account_tax_comparison", (
                RequirementSlot(
                    "해외 ETF 일반계좌 과세 기준",
                    ("해외", "ETF", "매매차익"),
                    2,
                    key="foreign_etf_general_account_tax",
                    retrieval_query="해외 ETF 일반계좌 매매차익 과세",
                    required_any_text_terms=("매매차익", "양도소득", "분배금"),
                ),
                RequirementSlot(
                    "해외 ETF 연금계좌 과세 시점",
                    ("연금저축", "IRP", "과세"),
                    2,
                    key="foreign_etf_pension_account_tax",
                    retrieval_query="해외 ETF 연금저축 IRP 과세이연 연금수령 과세",
                    required_any_text_terms=("과세이연", "연금수령", "연금 수령"),
                ),
                RequirementSlot(
                    "해외 ETF 계좌별 과세 예외·유의조건",
                    ("ETF", "과세", "2025"),
                    2,
                    key="foreign_etf_tax_condition",
                    retrieval_query="2025 해외 ETF 연금계좌 일반계좌 과세 유의사항",
                    required_any_text_terms=("2025", "2026", "세법", "과세"),
                ),
            ))
        if self._has_pension_account_tax_deferral_comparison(question):
            return self._plan("pension_account_tax_deferral_comparison", (
                RequirementSlot(
                    "일반계좌 과세 시점",
                    ("일반계좌", "과세"),
                    2,
                    key="general_account_tax_timing",
                    # Account-scope terms outrank generic "절세" examples and
                    # recover a chunk that states both sides of the timing
                    # comparison in its body.
                    retrieval_query="연금저축 IRP 일반 위탁 계좌 매매차익 분배금 과세이연",
                    required_body_any_text_terms=("일반계좌", "일반 계좌", "일반 위탁 계좌"),
                    required_any_text_terms=("과세", "세금"),
                ),
                RequirementSlot(
                    "연금계좌 과세이연 조건·시점",
                    ("연금계좌", "과세이연"),
                    2,
                    key="pension_account_tax_deferral",
                    retrieval_query="연금계좌 과세이연 연금수령 시 과세 일반계좌",
                    required_body_all_text_terms=("연금계좌",),
                    required_any_text_terms=("과세이연", "과세를 이연", "연금수령 시", "연금 수령 시"),
                ),
            ))
        if self._has_pension_savings_irp_tax_limit_comparison(question, extracted.accounts):
            return self._plan("pension_savings_irp_tax_limit_comparison", (
                RequirementSlot(
                    "연금저축 단독 세액공제 대상 한도",
                    ("연금저축", "세액공제"),
                    2,
                    key="pension_savings_only_deduction_limit",
                    retrieval_query="연금저축 단독 세액공제 대상 한도",
                    required_any_text_terms=("세액공제", "600", "400"),
                ),
                RequirementSlot(
                    "IRP 포함 합산 세액공제 대상 한도",
                    ("연금저축", "IRP", "세액공제"),
                    3,
                    key="pension_savings_irp_combined_deduction_limit",
                    retrieval_query="연금저축 IRP 합산 세액공제 대상 한도",
                    required_any_text_terms=("세액공제", "900", "700"),
                ),
            ))
        if self._has_pension_savings_irp_withdrawal_comparison(question, extracted.accounts):
            slots = [
                RequirementSlot(
                    "연금저축 인출 범위·조건",
                    ("연금저축", "인출"),
                    2,
                    key="pension_savings_withdrawal_scope",
                    retrieval_query="연금저축 일부 인출 중도인출 조건",
                    required_subject_terms=("연금저축",),
                    required_any_text_terms=("인출", "해지", "연금외수령"),
                    required_body_all_text_terms=("연금저축",),
                    # A generic ISA FAQ can mention that an 연금저축 account
                    # is withdrawable.  For this cross-account comparison,
                    # require the direct ``reason-independent`` withdrawal
                    # fact and keep every slot in the same source bundle.
                    required_body_any_text_terms=("사유무관", "사유와 무관"),
                    scope_group="pension_savings_irp_withdrawal_comparison",
                ),
                RequirementSlot(
                    "IRP 중도인출 법정사유",
                    ("IRP", "중도인출", "법정사유"),
                    2,
                    key="irp_withdrawal_legal_grounds_comparison",
                    retrieval_query="IRP 중도인출 법정사유 일부 인출",
                    required_subject_terms=("IRP",),
                    required_any_text_terms=("법정사유", "무주택", "요양", "파산", "개인회생"),
                    required_body_all_text_terms=("IRP", "중도인출"),
                    required_body_any_text_terms=("법정사유", "무주택", "요양", "파산", "개인회생"),
                    scope_group="pension_savings_irp_withdrawal_comparison",
                ),
            ]
            if any(marker in question for marker in ("세금", "과세", "세액")):
                slots.append(RequirementSlot(
                    "계좌별 인출 과세 처리",
                    ("연금저축", "IRP", "인출", "과세"),
                    3,
                    key="account_withdrawal_tax_treatment",
                    retrieval_query="연금저축 IRP 중도인출 과세 연금외수령",
                    required_subject_terms=("연금저축", "IRP"),
                    required_any_text_terms=("과세", "기타소득", "연금소득", "연금외수령"),
                    required_body_all_text_terms=("연금저축", "IRP", "인출"),
                    required_body_any_text_terms=("과세", "기타소득", "연금소득", "연금외수령"),
                    scope_group="pension_savings_irp_withdrawal_comparison",
                ))
            return self._plan("pension_savings_irp_withdrawal_comparison", tuple(slots))
        if self._has_pension_savings_irp_tax_and_withdrawal(question, extracted.accounts):
            return self._plan("pension_savings_irp_tax_and_withdrawal", (
                RequirementSlot(
                    "연금저축 세액공제 한도",
                    ("연금저축", "세액공제"),
                    2,
                    key="pension_savings_tax_deduction_limit",
                    retrieval_query="연금저축 세액공제 한도 IRP 합산",
                ),
                RequirementSlot(
                    "IRP 포함 합산 세액공제 한도",
                    ("IRP", "세액공제", "한도"),
                    2,
                    key="irp_combined_tax_deduction_limit",
                    retrieval_query="IRP 연금저축 합산 세액공제 한도",
                ),
                RequirementSlot(
                    "연금저축 인출 유연성",
                    ("연금저축", "사유", "인출"),
                    2,
                    key="pension_savings_withdrawal_flexibility",
                    retrieval_query="연금저축 사유 무관 중도인출 가능",
                    canonical_terms=("사유무관", "언제든"),
                ),
                RequirementSlot(
                    "IRP 인출 법정사유",
                    ("IRP", "법정사유", "인출"),
                    2,
                    key="irp_withdrawal_legal_grounds",
                    retrieval_query="IRP 중도인출 법정사유",
                    canonical_terms=("중도인출 사유",),
                ),
            ))
        if self._has_bond_fund_safety_premise(question):
            return self._plan("bond_fund_safety_premise", (
                RequirementSlot(
                    "위험등급 의미",
                    ("6등급", "위험"),
                    3,
                    key="risk_grade_meaning",
                    retrieval_query="6등급 채권형 예금자보호 원금손실 실제 수익률 변동성",
                    # A document title may say "채권" while the body says
                    # "투자 위험 등급".  Require the value-bearing
                    # volatility explanation so an aggregate asset-allocation
                    # table cannot stand in for an individual fund's grade.
                    required_all_text_terms=("6등급", "채권", "실제 수익률 변동성"),
                    required_text_pattern=r"[1-6]\s*등급",
                    canonical_terms=("채권", "매우 낮은 위험"),
                    scope_group="bond_fund_safety_subject",
                ),
                RequirementSlot(
                    "예금자보호 여부",
                    ("예금자보호", "보호"),
                    1,
                    key="deposit_protection_status",
                    retrieval_query="채권형 펀드 예금자보호 대상 아님",
                    scope_group="bond_fund_safety_subject",
                ),
                RequirementSlot(
                    "원금손실 가능성",
                    ("원금", "손실"),
                    2,
                    key="bond_fund_principal_loss",
                    retrieval_query="채권형 펀드 원금손실 가능 실적배당",
                    canonical_terms=("투자원본", "실적배당"),
                    scope_group="bond_fund_safety_subject",
                ),
            ), context_selection_required=True)
        if self._has_target_conversion_safety_premise(question):
            return self._plan("target_conversion_safety_premise", (
                RequirementSlot(
                    "목표전환 후 운용전략",
                    ("목표전환", "채권", "운용"),
                    2,
                    key="target_conversion_strategy",
                    retrieval_query="목표전환 주식관련자산 전부 매도 국내 채권 주로 투자",
                    # The product title alone ("운용전환일 이후 채권") is
                    # not its strategy.  Require a factual strategy statement.
                    required_any_text_terms=("국내 채권", "채권에 주로 투자", "주로 투자"),
                    scope_group="target_conversion_subject",
                ),
                RequirementSlot(
                    "전환 후 손실·성과 비보장",
                    ("보장", "손실"),
                    2,
                    key="target_conversion_not_guaranteed",
                    retrieval_query="목표전환형 펀드 원금손실 보장하지 않음",
                    canonical_terms=("가격 하락", "원금"),
                    scope_group="target_conversion_subject",
                ),
            ), context_selection_required=True)
        if self._has_irp_contribution_tax_limit(question, extracted.accounts):
            return self._plan("irp_contribution_and_tax_deduction_limit", (
                RequirementSlot(
                    "IRP 납입 한도",
                    ("IRP", "1,800", "납입"),
                    2,
                    key="irp_contribution_limit",
                    retrieval_query="IRP 연간 1800만원 납입 한도",
                    required_any_text_terms=("1,800", "1800"),
                ),
                RequirementSlot(
                    "IRP 세액공제 한도",
                    ("IRP", "900", "세액공제"),
                    2,
                    key="irp_tax_deduction_limit",
                    retrieval_query="IRP 연간 900만원 세액공제 한도",
                    required_any_text_terms=("900", "세액공제"),
                ),
            ))
        if self._has_retirement_income_irp_tax_timing(question, extracted.accounts):
            return self._plan("retirement_income_irp_tax_timing", (
                RequirementSlot(
                    "퇴직소득 IRP 이전 시 과세이연",
                    ("퇴직소득", "IRP", "과세이연"),
                    2,
                    key="retirement_income_transfer_tax_deferral",
                    retrieval_query="퇴직소득 IRP 이전 과세이연 퇴직소득세 환급",
                    required_any_text_terms=("과세이연", "퇴직소득세 환급", "과세를 이연"),
                ),
                RequirementSlot(
                    "IRP 연금 수령 시 과세 시점",
                    ("IRP", "연금 수령", "과세"),
                    2,
                    key="retirement_income_annuity_tax_timing",
                    retrieval_query="IRP 이연퇴직소득 연금 수령 시 과세",
                    required_any_text_terms=("연금수령 시", "연금 수령 시"),
                ),
            ))
        if self._has_db_dc_benefit_calculation(question, extracted.accounts):
            slots = [
                RequirementSlot("DB 급여 산정", ("DB", "퇴직급여", "평균임금"), 2, key="db_benefit"),
                RequirementSlot("DC 급여 산정", ("DC", "부담금", "운용"), 2, key="dc_benefit"),
            ]
            if self._has_operation_request(question):
                slots.extend(self._db_dc_operation_slots())
            return self._plan("db_dc_benefit_calculation", tuple(slots))
        if self._has_db_dc_conversion(question, extracted.accounts):
            slots = [RequirementSlot(
                "DB에서 DC 전환 가능 여부", ("DB", "DC", "전환 가능"), 3,
                key="conversion_eligibility", retrieval_query="DB DC 제도 전환 가능",
            )]
            if any(marker in question for marker in ("부담금", "회사 부담", "사용자 부담", "기여금")):
                slots.append(RequirementSlot(
                    "DC 회사 부담금 기준", ("DC", "부담금", "임금"), 2,
                    key="dc_employer_contribution", retrieval_query="DC 회사 부담금 연간 임금 12분의 1",
                    required_any_text_terms=("1/12", "12분의 1", "12 분의 1"),
                ))
            elif any(marker in question for marker in ("계산", "산정", "금액")):
                slots.append(RequirementSlot(
                    "전환 금액 산정", ("전환", "계산식", "평균임금"), 2,
                    key="conversion_amount",
                ))
            elif any(marker in question for marker in ("조건", "규약", "동의")):
                slots.append(RequirementSlot(
                    "제도전환 규약·동의 조건", ("퇴직연금규약", "동의"), 2,
                    key="conversion_conditions",
                ))
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
                RequirementSlot(
                    "해지 과세 예외",
                    ("부득이한", "연금외수령", "연금소득세"),
                    2,
                    max_term_span=400,
                    key="cancellation_exception",
                    required_any_text_terms=("5.5", "3.3", "연금소득세"),
                ),
            ))
        if "퇴직연금규약" in question and "동의" in question:
            return self._plan("policy_and_consent", (
                RequirementSlot("퇴직연금규약 내용", ("퇴직연금규약", "내용"), 2, key="policy_content"),
                RequirementSlot("근로자대표 동의", ("근로자대표", "동의"), 2, key="representative_consent"),
            ))
        if self._has_early_withdrawal_reason_request(question):
            return self._plan("early_withdrawal_legal_grounds", (
                RequirementSlot(
                    "퇴직 전 중도인출 가능 여부",
                    ("중도인출", "법정사유"),
                    2,
                    key="early_withdrawal_eligibility",
                    retrieval_query="퇴직 전 중도인출 법정사유 가능",
                ),
                RequirementSlot(
                    "퇴직 전 중도인출 법정사유",
                    ("중도인출", "무주택", "요양", "파산"),
                    3,
                    key="early_withdrawal_legal_grounds",
                    retrieval_query="중도인출 법정사유 무주택 요양 파산 개인회생",
                    required_any_text_terms=("무주택", "요양", "파산", "개인회생"),
                ),
            ))
        if self._has_irp_withdrawal_and_cancellation_comparison(question, extracted.accounts):
            return self._plan("irp_withdrawal_and_cancellation", (
                RequirementSlot(
                    "IRP 주택 관련 중도인출 사유",
                    ("IRP", "중도인출", "주택"), 2,
                    key="irp_housing_withdrawal", retrieval_query="IRP 중도인출 무주택 주택 구입 법정사유",
                    required_any_text_terms=("주택", "무주택"),
                ),
                RequirementSlot(
                    "IRP 일반 해지·인출 원칙",
                    ("IRP", "해지", "전액"), 2,
                    key="irp_cancellation_principle", retrieval_query="IRP 일반 해지 일부 인출 전액 해지",
                    required_any_text_terms=("해지", "인출"),
                ),
            ))
        if "중도인출" in question and any(marker in question for marker in ("절차", "준비", "서류", "증빙", "신청")):
            dc_scope = "DC" in extracted.accounts
            subject_terms = ("DC",) if dc_scope else ()
            scope_prefix = "DC " if dc_scope else ""
            return self._plan("withdrawal_condition_and_procedure", (
                RequirementSlot(
                    "중도인출 사유",
                    (*subject_terms, "중도인출", "사유"),
                    2 + len(subject_terms),
                    key="dc_withdrawal_conditions",
                    retrieval_query=f"{scope_prefix}중도인출 사유 증빙서류 중도인출신청서".strip(),
                    required_subject_terms=subject_terms,
                    required_any_text_terms=("근로자퇴직급여보장법", "법정사유", "사유와 요건"),
                    scope_group="withdrawal_condition_and_procedure",
                ),
                RequirementSlot(
                    "중도인출 절차",
                    (*subject_terms, "중도인출", "신청", "서류"),
                    2 + len(subject_terms),
                    key="withdrawal_procedure",
                    retrieval_query=f"{scope_prefix}중도인출 사유 증빙서류 중도인출신청서".strip(),
                    required_subject_terms=subject_terms,
                    required_any_text_terms=("중도인출신청서", "증빙서류", "서류제출"),
                    scope_group="withdrawal_condition_and_procedure",
                ),
            ))
        if self._has_dc_withdrawal_condition(question, extracted.accounts):
            return self._plan("dc_withdrawal_conditions", (
                RequirementSlot(
                    "DC 중도인출 가능 요건",
                    ("DC", "중도인출", "법정사유"),
                    3,
                    max_term_span=300,
                    key="dc_withdrawal_eligibility",
                    retrieval_query="DC 중도인출 법정사유 가능",
                ),
                RequirementSlot(
                    "DC 중도인출의 구체적 법정사유",
                    ("DC", "중도인출", "무주택", "요양", "파산"),
                    4,
                    max_term_span=600,
                    key="dc_withdrawal_legal_grounds",
                    retrieval_query="DC 중도인출 무주택 요양 파산 개인회생 법정사유",
                    required_any_text_terms=("무주택", "요양", "파산", "개인회생"),
                    # IRP 전용 중도인출 표가 DC라는 단어를 문서 앞부분에
                    # 함께 담은 경우를 DC의 상세 사유로 오인하지 않는다.
                    # DC 제도를 직접 설명한 근거만 후보로 인정한다.
                    required_text_pattern=r"dc\s*\(\s*확정기여형\s*\)",
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
        if self._has_db_dc_general_comparison(question, extracted.accounts):
            return self._plan("db_dc_general_comparison", (
                RequirementSlot(
                    "DB·DC 적립금 운용 주체",
                    ("DB", "DC", "적립금 운용", "회사", "근로자"),
                    4,
                    max_term_span=500,
                    key="db_dc_operation_party",
                    retrieval_query="DB DC 적립금 운용 주체 회사 근로자",
                ),
                RequirementSlot(
                    "DB·DC 퇴직급여 결정 방식",
                    ("DB", "DC", "퇴직급여", "평균임금", "부담금"),
                    4,
                    max_term_span=500,
                    key="db_dc_benefit_determination",
                    retrieval_query="DB DC 퇴직급여 평균임금 부담금 운용손익",
                ),
                RequirementSlot(
                    "DB·DC 부담금 구조",
                    ("DB", "DC", "부담금", "회사", "적립"),
                    4,
                    max_term_span=500,
                    key="db_dc_contribution_structure",
                    retrieval_query="DB DC 회사 부담금 적립 구조",
                ),
            ))
        if self._has_past_performance_premise(question):
            return self._plan("past_performance_premise", (
                RequirementSlot(
                    "과거 성과의 장래 성과 비보장",
                    ("과거", "실적", "보장"), 3,
                    key="past_performance_not_guarantee",
                    retrieval_query="과거의 투자실적이 장래에도 실현된다는 보장은 없습니다",
                    required_all_text_terms=("과거", "실적", "장래", "보장"),
                ),
                RequirementSlot(
                    "과거성과만으로 적합성을 정할 수 없음",
                    ("투자성향", "적합"),
                    2,
                    key="past_performance_suitability",
                    retrieval_query="투자성향 적합한 상품 신중한 투자결정",
                    required_all_text_terms=("투자성향", "적합"),
                ),
            ), context_selection_required=True)
        return self._plan("single_fact", ())

    def _product_plan(self, analysis) -> RequirementPlan | None:
        fields = list(analysis.extracted_entities.requested_fields)
        codes = analysis.product_codes
        if not codes:
            return None
        question = self._canonical_question(analysis.question)
        if any(marker in question for marker in ("위험등급이 바뀌", "위험등급 변경", "등급이 바뀌", "등급이 변하", "등급이 변하지", "등급이 고정", "변하지")):
            if "risk_grade" not in fields:
                fields.append("risk_grade")
            fields.append("risk_grade_changeability")
        if any(marker in question for marker in ("지수 추종", "지수에 연동", "지수를 따라")):
            if "investment_strategy" not in fields:
                fields.append("investment_strategy")
        if "비중" in question and any(marker in question for marker in ("주식", "채권", "자산", "투자")):
            if "investment_target" not in fields:
                fields.append("investment_target")
        if self._has_product_safety_request(analysis.question):
            for field_name in ("risk_grade", "principal_loss_possible", "principal_guarantee_status"):
                if field_name not in fields:
                    fields.append(field_name)
        if any(marker in analysis.question for marker in ("목표수익", "성과가 확정", "확정된다고", "수익이 확정")):
            for field_name in ("principal_loss_possible", "principal_guarantee_status"):
                if field_name not in fields:
                    fields.append(field_name)
        if "investment_risk" in fields and "principal_loss_possible" not in fields:
            fields.append("principal_loss_possible")
        if not fields:
            return None
        slots = []
        for code in codes:
            for field_name in fields:
                terms = (code,) if field_name == "product_name" else (code, *self._PRODUCT_FIELD_TERMS[field_name])
                equity_related_allocation = (
                    field_name == "investment_target" and "주식" in question and "비중" in question
                )
                index_tracking_strategy = field_name == "investment_strategy" and "지수" in question
                future_risk_grade_change = field_name == "risk_grade_changeability"
                retrieval_terms = self._PRODUCT_FIELD_RETRIEVAL_TERMS.get(
                    field_name, self._PRODUCT_FIELD_TERMS.get(field_name, ())
                )
                retrieval_subject = code
                if future_risk_grade_change:
                    # The field statement is a more selective query than the
                    # generic history tables.  Product identity is still
                    # enforced again by the matcher.
                    retrieval_terms = ("펀드", "위험 등급", "운용실적", "시장 상황", "변경될 수")
                if equity_related_allocation:
                    retrieval_terms = (*retrieval_terms, "주식 관련 자산", "60% 이상", "투자비율")
                field_evidence_terms = self._PRODUCT_FIELD_EVIDENCE_TERMS.get(field_name, ())
                if index_tracking_strategy:
                    field_evidence_terms = ("수익률에 연동", "지수의 수익률", "지수를 추종")
                elif equity_related_allocation:
                    # ``모투자신탁 90%`` is an outer-fund allocation, not the
                    # requested underlying equity-related allocation.
                    field_evidence_terms = ("주식관련", "주식 관련", "60% 이상", "60%이상")
                slots.append(
                    RequirementSlot(
                        name=f"{code} {field_name}",
                        terms=terms,
                        min_matches=1 if field_name == "product_name" else 2,
                        requires_title=field_name == "product_name",
                        key=f"{code}:{field_name}",
                        retrieval_query=f"{retrieval_subject} {' '.join(retrieval_terms)}".strip(),
                        reject_table_of_contents=True,
                        required_subject_terms=(code,),
                        required_any_text_terms=(
                            *field_evidence_terms,
                            # PDF table extraction often separates the field
                            # heading from its quantified value: ``투자대상 |
                            # 주식 | 60% 이상``.  This is still direct field
                            # evidence when the product identity and heading
                            # are required by the same slot.
                            *(("60% 이상", "60%이상") if equity_related_allocation else ()),
                        ),
                        forbidden_text_terms=("투자대상이 되는 자산가치",) if field_name == "investment_target" else (),
                        required_text_pattern=r"[1-6]\s*등급" if field_name == "risk_grade" else None,
                        required_all_text_terms=("주식", "투자") if equity_related_allocation else (("투자",) if field_name == "investment_target" else ()),
                        required_body_all_text_terms=(
                            ("위험등급", "변경") if future_risk_grade_change
                            else (("주식", "관련", "투자") if equity_related_allocation else ())
                        ),
                        required_body_any_text_terms=(
                            ("변경될 수", "변경될 가능성", "시장 상황") if future_risk_grade_change
                            else (("주식관련", "주식 관련") if equity_related_allocation else ())
                        ),
                        canonical_terms=("투자합니다", "투자하는", "투자 비중") if field_name == "investment_target" else (),
                    )
                )
        return self._plan("product_fields", tuple(slots), context_selection_required=True)

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
    def _has_early_withdrawal_reason_request(question: str) -> bool:
        return any(marker in question for marker in ("급여를 받기 전", "연금 돈을 빼", "연금돈을 빼", "미리 인출", "조기 인출")) and any(
            marker in question for marker in ("사유", "조건", "요건", "가능")
        )

    @staticmethod
    def _has_retirement_income_irp_tax_timing(question: str, accounts: list[str]) -> bool:
        return "IRP" in accounts and "퇴직소득" in question and any(
            marker in question for marker in ("이전", "이체", "입금")
        ) and any(marker in question for marker in ("과세", "세금", "시점"))

    @staticmethod
    def _has_irp_contribution_tax_limit(question: str, accounts: list[str]) -> bool:
        return "IRP" in accounts and any(marker in question for marker in ("납입", "입금", "불입", "넣으", "적립")) and any(
            marker in question for marker in ("세액공제", "전액 공제", "공제 대상")
        )

    @staticmethod
    def _has_irp_withdrawal_and_cancellation_comparison(question: str, accounts: list[str]) -> bool:
        return "IRP" in accounts and any(marker in question for marker in ("중도인출", "인출")) and any(
            marker in question for marker in ("해지", "일반")
        )

    @staticmethod
    def _has_past_performance_premise(question: str) -> bool:
        past_performance = any(marker in question for marker in ("과거 수익률", "과거 성과", "과거 실적", "투자실적", "지난 수익률", "지난 성과")) or (
            "지난" in question and any(marker in question for marker in ("수익률", "성과", "실적"))
        )
        return past_performance and any(
            marker in question for marker in ("앞으로", "장래", "계속", "보장", "확정", "좋은 선택")
        )

    @staticmethod
    def _has_db_dc_general_comparison(question: str, accounts: list[str]) -> bool:
        return {"DB", "DC"} <= set(accounts) and any(
            marker in question for marker in ("차이", "비교", "어떻게 다른", "각각", "구별", "대조", "대비")
        )

    @staticmethod
    def _has_product_safety_request(question: str) -> bool:
        return any(marker in question for marker in (
            "안전해", "안전한", "안전하", "원금 보장", "원금보장",
            "원금이 보장", "손실 가능성", "손실이 없", "손실 없", "예금자보호",
        ))

    @staticmethod
    def _has_participant_education(question: str, accounts: tuple[str, ...]) -> bool:
        # 일반적인 "가입자 교육" 문의는 기존 simple retrieval 경로를 유지한다.
        # DB/DC 제도 범위를 함께 명시한 경우에만 제도별 책임·주기·위탁이라는
        # multi-evidence contract를 만든다.
        return (
            bool({"DB", "DC"} & set(accounts))
            or "위탁" in question
            or "외부에 맡" in question
            or "외부 기관" in question
        ) and "가입자" in question and "교육" in question and any(
            marker in question for marker in ("누가", "주기", "얼마나", "위탁", "실시", "횟수", "직접", "맡")
        )

    @staticmethod
    def _has_in_kind_transfer_request(question: str, accounts: list[str]) -> bool:
        return any(marker in question for marker in ("실물이전", "금융회사만 바꾸", "상품을 팔지")) and (
            {"DB", "DC"} <= set(accounts) or "IRP" in accounts
        )

    @staticmethod
    def _has_retirement_etf_restriction(question: str, accounts: list[str]) -> bool:
        return "ETF" in question.upper() and any(marker in question for marker in ("레버리지", "인버스")) and (
            "DC" in accounts or "IRP" in accounts or "퇴직연금" in question
        )

    @staticmethod
    def _canonical_question(question: str) -> str:
        """Map safe surface-form variants into existing requirement intents.

        This is intentionally a small, question-semantic normalisation layer,
        not question-ID routing: every substitution corresponds to the same
        closed factual action already represented by a requirement schema.
        """
        canonical = normalize_pension_question(question)
        for variant in ("구별", "가려내", "가려 봐", "대조", "대비"):
            canonical = canonical.replace(variant, "비교")
        for variant in ("중간에 꺼내", "중간 꺼내", "중간에 빼", "중간 빼"):
            canonical = canonical.replace(variant, "중도인출")
        return canonical

    @staticmethod
    def _has_isa_maturity_transfer(question: str, accounts: list[str]) -> bool:
        return "ISA" in question.upper() and "만기" in question and any(
            marker in question for marker in ("옮기", "옮길", "이전", "전환", "전환납입")
        ) and ("IRP" in accounts or "연금저축" in accounts or "연금계좌" in question)

    @staticmethod
    def _has_isa_transfer_tax_timing_request(question: str) -> bool:
        return any(marker in question for marker in ("세금", "과세", "비과세")) and any(
            marker in question for marker in ("언제", "시점", "인출", "수령", "이전한 금액", "전환금")
        )

    @staticmethod
    def _has_irp_eligibility_request(question: str, accounts: list[str]) -> bool:
        return "IRP" in accounts and any(
            marker in question for marker in ("가입할 수", "가입할수", "가입 대상", "가입대상", "누가 가입", "어떤 사람")
        )

    @staticmethod
    def _has_pension_savings_irp_tax_and_withdrawal(question: str, accounts: list[str]) -> bool:
        return {"연금저축", "IRP"} <= set(accounts) and any(
            marker in question for marker in ("세액공제", "공제 한도", "공제한도")
        ) and any(
            marker in question for marker in ("인출", "중간에 돈", "유연성", "꺼내")
        )

    @staticmethod
    def _has_pension_savings_irp_tax_limit_comparison(question: str, accounts: list[str]) -> bool:
        return {"연금저축", "IRP"} <= set(accounts) and any(
            marker in question for marker in ("세액공제", "공제 대상", "공제한도", "공제 한도")
        ) and not any(marker in question for marker in ("인출", "중도", "해지", "꺼내", "빼"))

    @staticmethod
    def _has_pension_savings_irp_withdrawal_comparison(question: str, accounts: list[str]) -> bool:
        return {"연금저축", "IRP"} <= set(accounts) and any(
            marker in question for marker in ("인출", "중도", "해지", "빼", "꺼내")
        ) and not any(marker in question for marker in ("세액공제", "공제 한도", "공제한도"))

    @staticmethod
    def _has_pension_account_tax_deferral_comparison(question: str) -> bool:
        return "연금계좌" in question and "일반계좌" in question and any(
            marker in question for marker in ("과세이연", "과세 이연", "절세", "세금", "과세")
        )

    @staticmethod
    def _has_foreign_etf_account_tax_comparison(question: str, accounts: list[str]) -> bool:
        return "ETF" in question.upper() and any(
            marker in question for marker in ("해외", "국내 상장 해외")
        ) and ("일반계좌" in question or "연금계좌" in question or {"연금저축", "IRP"} <= set(accounts)) and any(
            marker in question for marker in ("세금", "과세", "비과세", "매매차익", "분배금")
        )

    @staticmethod
    def _has_bond_fund_safety_premise(question: str) -> bool:
        return "채권형" in question and any(marker in question for marker in ("예금자보호", "원금보장", "원금 보장"))

    @staticmethod
    def _has_target_conversion_safety_premise(question: str) -> bool:
        return "목표전환" in question and any(marker in question for marker in ("채권 중심", "가격", "내려", "손실"))

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
            RequirementSlot(
                "DB 적립금 운용",
                ("DB", "회사", "적립금 운용"),
                3,
                max_term_span=400,
                key="db_operation",
                retrieval_query="확정급여형 DB 운용 주체 회사 적립금",
            ),
            RequirementSlot(
                "DC 적립금 운용",
                ("DC", "근로자", "적립금 운용"),
                3,
                max_term_span=400,
                key="dc_operation",
                retrieval_query="확정기여형 DC 운용 주체 근로자 적립금",
            ),
        ]

    @staticmethod
    def _has_irp_annuity_age_and_duration(question: str, accounts: list[str]) -> bool:
        has_annuity = "연금" in question and any(marker in question for marker in ("수령", "지급", "받"))
        has_age = any(marker in question for marker in ("연령", "나이", "몇 살", "55세", "55 세"))
        has_duration = any(marker in question for marker in ("기간", "몇 년", "몇년", "5년", "5 년"))
        return "IRP" in accounts and has_annuity and has_age and has_duration

    @staticmethod
    def _plan(
        category: str,
        slots: tuple[RequirementSlot, ...],
        *,
        context_selection_required: bool = False,
    ) -> RequirementPlan:
        return RequirementPlan(
            case=RequirementCase(
                question_id=f"dynamic:{category}",
                role="p14_requirement_builder",
                slots=slots,
                context_selection_required=context_selection_required,
            ),
            category=category,
        )
