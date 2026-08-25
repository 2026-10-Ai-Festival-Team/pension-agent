"""근거 검증 뒤 적용하는 보수적 금융 답변 표현 정책."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResult
from src.orchestration.evidence_assessor import EvidenceAssessment
from src.orchestration.query_analyzer import QueryAnalysis


@dataclass(frozen=True)
class RecommendationPolicyDecision:
    """실제 사용자 화면에서만 적용하는 보수적 추천 행동 결정."""

    is_recommendation_context: bool
    profile_complete: bool
    missing_conditions: tuple[str, ...]
    reasons: tuple[str, ...]
    preference_conflict: bool = False


@dataclass(frozen=True)
class ProductReferenceDecision:
    """상태 없는 API에서 상품 식별자 누락 여부를 표현한다."""

    requires_product_identification: bool


class FinancialAnswerPolicy:
    """원문 근거·정보 한계·상품 추천 원칙을 사용자 응답에 일관되게 적용한다."""

    def format_answer(
        self,
        answer: str,
        analysis: QueryAnalysis,
        cited_contexts: Iterable[SearchResult],
    ) -> str:
        cited = list(cited_contexts)
        answer = self._complete_source_bound_document_request(answer, analysis, cited)
        sections = ["[답변]", answer.strip(), "", "[근거]"]
        sections.extend(self._citation(item) for item in cited)
        notices = self._notices(analysis)
        if notices:
            sections.extend(["", "[유의사항]"])
            sections.extend(f"- {notice}" for notice in notices)
        return "\n".join(sections)

    @staticmethod
    def _complete_source_bound_document_request(
        answer: str,
        analysis: QueryAnalysis,
        cited_contexts: Iterable[SearchResult],
    ) -> str:
        """질문이 서류 목록을 요구했을 때 원문에 있는 대표 예시를 누락하지 않는다.

        이 보완은 새로운 금융 사실을 생성하지 않는다. 인용된 원문에 신청서와
        주택구입 사유의 구비서류가 함께 있을 때만, 질문이 요구한 서류 항목을
        원문 표현 범위에서 명시한다. 다른 법정사유의 서류까지 일반화하지 않는다.
        """
        question = analysis.question.replace(" ", "")
        asks_for_documents = any(marker in question for marker in ("증빙", "서류", "구비"))
        asks_for_early_withdrawal = "중도인출" in question or (
            "퇴직" in question
            and "적립금" in question
            and any(marker in question for marker in ("인출", "꺼내", "꺼낼", "빼", "뺄", "찾", "찾을"))
        )
        evidence_text = "\n".join(item.text for item in cited_contexts)
        document_markers = (
            "중도인출신청서",
            "주민등록등본",
            "건물등기사항증명서",
            "지방세 세목별 과세증명서",
        )
        if not (asks_for_documents and asks_for_early_withdrawal):
            return answer
        if not all(marker in evidence_text for marker in document_markers):
            return answer
        if "주민등록등본" in answer and "건물등기사항증명서" in answer:
            return answer
        return (
            answer.rstrip()
            + "\n\n원문에 나온 무주택자 주택구입 사유의 서류 예시는 중도인출신청서, "
            "주민등록등본, 현 거주지 주소의 건물등기사항증명서, 지방세 세목별 과세증명서, "
            "매매·분양·공급계약서 사본 등입니다. 다른 법정사유는 요구되는 증빙서류가 다를 수 있습니다."
        )

    def recommendation_decision(self, analysis: QueryAnalysis) -> RecommendationPolicyDecision:
        """추천 표현과 투자성향 서술을 별도의 사용자 보호 정책으로 분류한다.

        기존 QueryAnalyzer의 retrieval intent는 바꾸지 않는다. 이 판단은 최종
        사용자 행동만 제어하며, 금융 사실을 새로 만들지 않는다.
        """

        question = analysis.question.replace(" ", "")
        safety_premise = self._is_past_performance_safety_premise(question)
        explicit_recommendation = not safety_premise and any(
            marker in question
            for marker in (
                "추천", "골라", "선정", "최고", "가장좋은",
                "수익률제일높", "수익률높은", "무조건",
            )
        )
        has_period = bool(re.search(r"\d+\s*년", question)) or "투자기간" in question
        has_risk_profile = bool(re.search(r"변동.{0,2}감수", question)) or any(
            marker in question
            for marker in (
                "위험성향", "위험감수", "변동감수", "변동성감수", "안전", "안정",
                "변동은감수", "변동을감수", "보수적", "공격적", "적극적", "원금손실",
                "손실은최대한", "손실을최대한", "손실회피",
            )
        )
        explicit_purpose = any(
            marker in question
            # 명사 ``투자``는 투자설명서·투자비용에도 나타나므로 목적 신호가 아니다.
            # 실제 운용 의도를 나타내는 명시적 목적 또는 동사형 표현만 사용한다.
            for marker in ("운용목적", "노후", "퇴직연금", "노후준비", "장기투자")
        )
        # 계좌 유형을 이미 특정한 추천 요청에서는 단순 기간만으로 운용 목적을
        # 추론하지 않는다. 예를 들어 "연금저축으로 8년"은 노후·중도사용 등
        # 목적을 구별할 수 없으므로 첫 응답에서 확인해야 한다. 반면 계좌를
        # 특정하지 않은 일반 투자 프로필의 "10년 투자, 공격적"은 후보 비교
        # 안내를 위한 최소 목적 신호로 유지한다.
        generic_horizon_purpose = bool(re.search(r"\d+\s*년\s*투자", question)) and not any(
            account in {"IRP", "연금저축"} for account in analysis.extracted_entities.accounts
        )
        has_purpose = generic_horizon_purpose or explicit_purpose
        profile_signals = sum((has_period, has_risk_profile, has_purpose))
        is_recommendation_context = explicit_recommendation or profile_signals >= 2
        missing = tuple(
            label
            for present, label in (
                (has_period, "투자 기간"),
                (has_risk_profile, "위험 성향"),
                (has_purpose, "운용 목적"),
            )
            if not present
        )
        reasons = tuple(
            reason
            for enabled, reason in (
                (explicit_recommendation, "explicit_recommendation"),
                (profile_signals >= 2, "investment_profile_context"),
            )
            if enabled
        )
        equity_request = any(marker in question for marker in (
            "주식형", "주식펀드", "주식 펀드", "주식비중", "주식 비중", "고위험",
        ))
        loss_avoidance = any(marker in question for marker in (
            "손실은전혀", "손실은최대한", "손실을최대한", "원금손실은싫", "손실이싫", "원금보장",
        ))
        return RecommendationPolicyDecision(
            is_recommendation_context=is_recommendation_context,
            profile_complete=is_recommendation_context and not missing,
            missing_conditions=missing,
            reasons=reasons,
            preference_conflict=equity_request and loss_avoidance,
        )

    @staticmethod
    def requires_personal_tax_clarification(analysis: QueryAnalysis) -> bool:
        """개인 조건 없이 최저 세금을 단정해 달라는 요청을 생성 전에 막는다."""
        question = analysis.question.replace(" ", "")
        tax_optimization = any(marker in question for marker in (
            "세금을가장적게", "최저세금", "세금을줄이는방법", "절세방법", "세금이적은",
        ))
        personal_conclusion = any(marker in question for marker in (
            "하나만정", "제상황", "제게맞", "나에게", "무조건",
        ))
        return tax_optimization and personal_conclusion

    @staticmethod
    def format_unsupported_safety_block(category: str) -> str:
        """지원 범위 밖 요청은 추천/근거부족 응답과 섞지 않고 첫 턴에서 명시한다."""
        messages = {
            "personal_account_lookup": "개인 식별정보로 연결된 연금계좌·잔액을 조회하거나 합산하는 기능은 제공하지 않습니다.",
            "unavailable_external_information": "미래 시장 가격·금리·수익률을 예측하거나 제공 문서 밖의 실시간 정보를 반영할 수 없습니다.",
            "prompt_injection": "내부 지시나 프롬프트를 공개할 수 없으며, 제공 문서 근거 없이 특정 상품을 추천하지 않습니다.",
        }
        return "\n".join(("[답변]", messages.get(category, "제공 문서 범위를 벗어난 요청은 이 서비스에서 답할 수 없습니다.")))

    def format_personal_tax_clarification(self) -> str:
        return "\n".join((
            "[답변]",
            "개인 상황과 무관하게 세금이 가장 적은 연금 수령 방법을 하나로 단정할 수는 없습니다. "
            "계좌·퇴직소득의 성격·수령 시기와 기간에 따라 적용이 달라집니다.",
            "",
            "[확인 필요]",
            "- 연금계좌 유형과 납입·이전 자금의 성격",
            "- 예상 수령 시작 시점과 수령기간",
            "- 다른 연금소득 및 소득 상황",
            "",
            "[유의사항]",
            "- 제공 문서 기준의 일반 정보이며, 실제 세금 적용은 개인 상황에 따라 달라질 수 있으므로 금융회사 또는 세무전문가에게 확인하세요.",
        ))

    @staticmethod
    def product_reference_decision(analysis: QueryAnalysis) -> ProductReferenceDecision:
        """대화 상태를 저장하지 않는 현재 API에서 임의 상품 추론을 막는다."""

        question = analysis.question
        generic_reference = any(marker in question for marker in ("이 상품", "해당 상품", "이 펀드", "이것"))
        risk_or_product_field = any(
            marker in question for marker in ("안전", "위험", "위험등급", "수익", "보수", "투자대상")
        )
        return ProductReferenceDecision(
            requires_product_identification=(
                generic_reference and risk_or_product_field and not analysis.product_codes
            )
        )

    def format_recommendation_clarification(
        self, decision: RecommendationPolicyDecision
    ) -> str:
        """조건이 부족한 추천성 요청은 생성하지 않고 필요한 정보를 되묻는다."""

        sections = [
            "[답변]",
            "특정 상품을 추천하거나 가장 좋은 상품이라고 단정하기보다, "
            "먼저 투자 조건을 확인한 뒤 원본 문서의 위험등급·투자대상·총보수를 비교해 드릴 수 있습니다.",
            "",
            "[확인 필요]",
        ]
        if decision.preference_conflict:
            sections[1] = (
                "원금 손실을 원하지 않는 조건과 주식형 상품 요청은 함께 충족되기 어렵습니다. "
                "특정 상품을 추천하기 전에 손실 감수 범위와 투자 조건을 확인해야 합니다."
            )
        sections.extend(f"- {item}" for item in decision.missing_conditions)
        sections.extend(["", "[유의사항]", f"- {self._product_risk_notice()}"])
        return "\n".join(sections)

    def format_recommendation_comparison_guidance(
        self, decision: RecommendationPolicyDecision
    ) -> str:
        """조건이 있어도 단일 상품의 매수·매도 추천으로 답하지 않는다."""

        assert decision.profile_complete
        return "\n".join(
            [
                "[답변]",
                "입력한 투자 기간·위험 성향·운용 목적을 확인했습니다. 제공 문서에 있는 후보 상품은 "
                "위험등급, 투자대상, 총보수 기준으로 비교할 수 있지만, 특정 상품이 최고·무조건 안전하다고 "
                "단정하거나 매수·매도를 권유하지는 않습니다.",
                "",
                "[확인 필요]",
                "- 비교할 상품명 또는 상품코드",
                "- 현재 계좌의 보유 상품 및 분산투자 여부",
                "",
                "[유의사항]",
                f"- {self._product_risk_notice()}",
            ]
        )

    def format_product_reference_clarification(self) -> str:
        return "\n".join(
            [
                "[답변]",
                "현재 API는 이전 대화의 상품을 기억하지 않으므로, 안전성·위험등급을 확인할 상품을 특정할 수 없습니다.",
                "",
                "[확인 필요]",
                "- 상품명 또는 상품코드",
                "",
                "[유의사항]",
                f"- {self._product_risk_notice()}",
            ]
        )

    def format_insufficient(
        self,
        assessment: EvidenceAssessment,
        analysis: QueryAnalysis,
    ) -> str:
        sections = ["[답변]"]
        if assessment.reason == "conditional_recommendation_requires_user_conditions":
            sections.append(
                "특정 상품을 추천하거나 최선의 상품이라고 단정하기보다, "
                "먼저 필요한 조건을 확인한 뒤 문서상 특성을 비교해 드릴 수 있습니다."
            )
            sections.extend(["", "[확인 필요]"])
            sections.extend(f"- {item}" for item in assessment.missing_requirements)
        elif assessment.reason == "unsupported_or_personal_information":
            sections.append(
                "개인 계좌 정보·실시간 외부 정보 또는 제공 문서 범위를 벗어난 내용은 "
                "이 서비스에서 확인할 수 없습니다."
            )
        elif assessment.reason == "primary_original_evidence_missing":
            sections.append(
                "보강 정보는 확인됐지만, 제공된 원본 문서에서 금융 사실을 확정할 "
                "1차 근거를 확인하지 못했습니다. 추측하여 답변하지 않겠습니다."
            )
        else:
            sections.append(
                "제공된 원본 문서에서 질문에 답할 충분한 근거를 확인하지 못했습니다. "
                "추측하여 답변하지 않겠습니다."
            )
        sections.extend(["", "[유의사항]"])
        sections.extend(f"- {notice}" for notice in self._notices(analysis, insufficient=True))
        return "\n".join(sections)

    def format_generation_failure(self, analysis: QueryAnalysis) -> str:
        """근거 부족과 응답 형식 검증 실패를 사용자에게 구분해 알린다."""
        sections = [
            "[답변]",
            "관련 원본 근거는 찾았지만, 응답 형식을 안전하게 검증하지 못해 답변을 표시하지 않았습니다. "
            "잠시 후 같은 질문을 다시 시도해 주세요.",
            "",
            "[유의사항]",
        ]
        notices = self._notices(analysis)
        sections.extend(f"- {notice}" for notice in (notices or [
            "근거가 확인되지 않은 내용을 추측하여 답변하지 않습니다."
        ]))
        return "\n".join(sections)

    @staticmethod
    def is_primary_original(context: SearchResult) -> bool:
        return (
            context.source_type == SourceType.ORIGINAL
            and context.authority_level == AuthorityLevel.PRIMARY
        )

    def _notices(self, analysis: QueryAnalysis, insufficient: bool = False) -> list[str]:
        question = analysis.question
        notices: list[str] = []
        if analysis.intent == "tax" or any(word in question for word in ("세금", "과세", "공제", "세액", "소득세")):
            notices.append(
                "제공 문서 기준의 일반 정보입니다. 실제 세금 적용은 소득, 계좌, 수령 방식, "
                "적용 시점에 따라 달라질 수 있으므로 금융회사 또는 세무전문가에게 확인하세요."
            )
        if any(word in question for word in ("법률", "법적", "소송", "압류", "상속", "판례")):
            notices.append(
                "제공 문서는 일반 안내 자료입니다. 법률 해석이나 권리 판단은 개별 사실관계에 따라 "
                "달라질 수 있으므로 필요하면 전문가와 확인하세요."
            )
        if analysis.intent in {"conditional_recommendation", "product_explanation"}:
            notices.append(
                "문서에 기재된 위험등급·보수·투자대상 등 사실만 비교하며, 특정 상품의 매수·매도나 "
                "최선의 상품을 권유하지 않습니다. 최종 선택은 본인의 목적과 위험 감수 수준을 고려해 판단하세요."
            )
        if self._is_product_risk_question(analysis):
            notices.append(self._product_risk_notice())
        if insufficient and not notices:
            notices.append("근거가 부족한 경우에는 답변을 추정하지 않고 확인이 필요한 사항을 안내합니다.")
        return notices

    @staticmethod
    def _is_product_risk_question(analysis: QueryAnalysis) -> bool:
        question = analysis.question
        return bool(analysis.product_codes) or (
            any(word in question for word in ("상품", "펀드"))
            and any(word in question for word in ("위험", "안전", "수익", "보수", "투자대상"))
        )

    @staticmethod
    def _is_past_performance_safety_premise(question: str) -> bool:
        past_performance = any(marker in question for marker in ("과거수익률", "과거성과", "과거실적", "투자실적", "지난수익률", "지난성과")) or (
            "지난" in question and any(marker in question for marker in ("수익률", "성과", "실적"))
        )
        return past_performance and any(
            marker in question for marker in ("앞으로", "장래", "계속", "보장", "확정", "가장좋은")
        )

    @staticmethod
    def _product_risk_notice() -> str:
        return (
            "위험등급·투자대상·총보수와 원금보장 여부는 해당 상품의 원본 설명서에서 확인해야 합니다. "
            "실적배당형 상품을 원금보장 또는 손실이 없다고 단정하지 않습니다."
        )

    @staticmethod
    def _citation(item: SearchResult) -> str:
        if item.locator.page_start:
            location = f"{item.locator.page_start}페이지"
        elif item.locator.slide_start:
            location = f"{item.locator.slide_start}슬라이드"
        elif item.locator.sheet:
            location = f"{item.locator.sheet} 시트"
        else:
            location = "위치 정보 없음"
        as_of = f", 기준일 {item.as_of_date}" if item.as_of_date else ""
        return f"- [출처: {item.source_path}, {location}{as_of}, {item.chunk_id}]"
