"""Host-owned required-fact completeness contract for selected evidence.

The contract is deliberately narrow: it only covers canonical requirements
whose fact units are already explicitly bound to selected original evidence.
It never supplies a new source or derives a new financial fact.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from src.models.retrieval import SearchResult


def _normalise(value: str) -> str:
    return "".join(value.casefold().split())


@dataclass(frozen=True)
class RequiredFact:
    key: str
    prompt_text: str
    evidence_anchors: tuple[str, ...]
    answer_aliases: tuple[str, ...]


@dataclass(frozen=True)
class CompletenessAssessment:
    applicable: bool
    required_fact_keys: tuple[str, ...]
    missing_fact_keys: tuple[str, ...]
    evidence_contract_valid: bool


@dataclass(frozen=True)
class HostCompletion:
    """A strictly extracted supplement for facts the model omitted.

    ``text`` is composed only from templates whose values were found in the
    currently selected direct evidence.  It is never a fallback answer, a
    retrieval expansion, or a new factual inference.
    """

    applicable: bool
    completed_fact_keys: tuple[str, ...]
    unresolved_fact_keys: tuple[str, ...]
    supporting_chunk_ids: tuple[str, ...]
    text: str


_CONTRACTS: dict[str, tuple[RequiredFact, ...]] = {
    "DC.benefit_determination": (
        RequiredFact(
            "dc_benefit_contribution",
            "DC형 퇴직급여 산정에 사용자 부담금 누계액이 반영됨을 설명",
            ("부담금 누계액",),
            ("부담금",),
        ),
        RequiredFact(
            "dc_benefit_investment_return",
            "DC형 퇴직급여 산정에 운용손익이 반영됨을 설명",
            ("운용손익",),
            ("운용성과", "운용손익", "운용 결과"),
        ),
    ),
    "pension_savings.early_withdrawal.allowed_reasons": (
        RequiredFact(
            "pension_savings_early_withdrawal_compelling_reason",
            "연금저축 연금수령 전 인출은 부득이한 사유와 구분됨을 설명",
            ("부득이한 사유",),
            ("부득이한 사유",),
        ),
    ),
    "IRP.early_withdrawal.allowed_reasons": (
        RequiredFact(
            "irp_early_withdrawal_legal_grounds",
            "IRP의 연금수령 전 중도인출 사유가 법으로 열거된 법정사유임을 설명",
            ("중도인출 사유를 법으로 열거",),
            ("법정사유", "법정 사유"),
        ),
    ),
    "DC.early_withdrawal.required_documents": (
        RequiredFact(
            "dc_early_withdrawal_document_requirement",
            "DC 중도인출은 법정사유에 맞는 증빙서류의 구비·제출이 필요함을 설명",
            ("증빙서류",),
            ("증빙서류", "증빙 서류"),
        ),
    ),
    "pension_account.investment_income.tax_timing": (
        RequiredFact(
            "pension_account_investment_income_deferral",
            "연금계좌 운용수익의 과세이연을 설명",
            ("과세이연",),
            ("과세이연", "세금 납부가 연기"),
        ),
    ),
    "pension_account.investment_income.not_tax_exempt": (
        RequiredFact(
            "pension_account_investment_income_not_exempt",
            "연금계좌 운용수익이 면세가 아니라 연금수령 시 과세됨을 설명",
            ("연금수령 시 연금소득",),
            ("면세", "비과세", "연금소득"),
        ),
    ),
    "product.risk_grade.historical": (
        RequiredFact(
            "risk_history_before_grade",
            "과거 변경 이력에서 변경 전 위험등급을 실제 등급값과 함께 설명",
            ("변경전 위험등급",),
            ("변경전", "변경 전"),
        ),
        RequiredFact(
            "risk_history_after_grade",
            "과거 변경 이력에서 변경 후 위험등급을 실제 등급값과 함께 설명",
            ("변경후 위험등급",),
            ("변경후", "변경 후"),
        ),
        RequiredFact(
            "risk_history_reason",
            "각 위험등급 변경의 사유를 설명",
            ("위험등급 변경사유",),
            ("변경사유", "변경 사유"),
        ),
    ),
    "retirement_income.IRP_transfer.tax_timing": (
        RequiredFact(
            "irp_tax_deferral",
            "운용수익은 연금 수령 시까지 과세이연되고 운용 중 세금이 없음을 설명",
            ("연금 수령 시까지 과세이연", "운용 중 세금 없음"),
            ("과세이연",),
        ),
        RequiredFact(
            "irp_tax_at_pension_receipt",
            "운용수익 과세는 연금 수령 시점에 이루어짐을 설명",
            ("운용수익 과세", "연금수령"),
            ("연금수령", "연금 수령"),
        ),
        RequiredFact(
            "irp_tax_payment_distributed",
            "세금 납부시점은 연금 수령 시마다 분산됨을 설명",
            ("세금납부시점", "연금 수령시마다 분산"),
            ("분산",),
        ),
    ),
    "ISA.transfer.additional_tax_credit": (
        RequiredFact(
            "isa_transfer_additional_credit_rate",
            "ISA 만기자금 전환금액의 추가 세액공제 비율을 설명",
            ("10%",),
            ("10%",),
        ),
        RequiredFact(
            "isa_transfer_additional_credit_cap",
            "ISA 만기자금 전환에 따른 추가 세액공제 한도를 설명",
            ("300만원",),
            ("300만원", "300만 원"),
        ),
    ),
}


class RequiredFactCompletenessGate:
    """Assess only fact contracts justified by current selected contexts."""

    def facts_for(self, requirements: Iterable[str]) -> tuple[RequiredFact, ...]:
        facts: list[RequiredFact] = []
        seen: set[str] = set()
        for requirement in requirements:
            for fact in _CONTRACTS.get(requirement, ()):
                if fact.key not in seen:
                    facts.append(fact)
                    seen.add(fact.key)
        return tuple(facts)

    def assess(
        self,
        requirements: Iterable[str],
        contexts: Iterable[SearchResult],
        answer: str,
    ) -> CompletenessAssessment:
        facts = self.facts_for(requirements)
        if not facts:
            return CompletenessAssessment(False, (), (), True)
        evidence = _normalise("\n".join(context.text for context in contexts))
        evidence_valid = all(all(_normalise(anchor) in evidence for anchor in fact.evidence_anchors) for fact in facts)
        normalized_answer = _normalise(answer)
        missing = tuple(
            fact.key for fact in facts
            if not any(_normalise(alias) in normalized_answer for alias in fact.answer_aliases)
        )
        return CompletenessAssessment(True, tuple(fact.key for fact in facts), missing, evidence_valid)

    @staticmethod
    def _supporting_contexts(contexts: Iterable[SearchResult], anchors: tuple[str, ...]) -> tuple[SearchResult, ...]:
        """Return only selected contexts which contain every exact anchor."""
        return tuple(
            context for context in contexts
            if all(_normalise(anchor) in _normalise(context.text) for anchor in anchors)
        )

    @staticmethod
    def _latest_risk_history_row(contexts: Iterable[SearchResult]) -> tuple[str, str, str, str, str] | None:
        """Extract one exact row from the selected risk-history table.

        The source table is a pipe-delimited PDF extraction.  We intentionally
        preserve its newest row rather than calculating or generalising a
        risk-grade trend.
        """
        date_pattern = re.compile(r"^\s*(20\d{2}\.\d{2}\.\d{2})\s*\|")
        for context in contexts:
            if "변경전 위험등급" not in context.text or "위험등급 변경사유" not in context.text:
                continue
            rows: list[dict[str, str]] = []
            current: dict[str, str] | None = None
            for raw_line in context.text.splitlines():
                match = date_pattern.match(raw_line)
                if match:
                    if current is not None:
                        rows.append(current)
                    cells = [cell.strip() for cell in raw_line.split("|")]
                    if len(cells) < 10 or not re.fullmatch(r"[1-6]등급", cells[3]) or not re.fullmatch(r"[1-6]등급", cells[6]):
                        current = None
                        continue
                    current = {
                        "date": match.group(1), "before": cells[3], "after": cells[6],
                        "reason": cells[9].lstrip("- ").strip(),
                    }
                elif current is not None:
                    continuation = " ".join(cell.strip() for cell in raw_line.split("|") if cell.strip()).lstrip("- ").strip()
                    if continuation:
                        current["reason"] = f"{current['reason']} {continuation}".strip()
            if current is not None:
                rows.append(current)
            if rows:
                latest = rows[-1]
                if latest["reason"]:
                    return latest["date"], latest["before"], latest["after"], latest["reason"], context.chunk_id
        return None

    def complete_missing_facts(
        self,
        requirements: Iterable[str],
        contexts: Iterable[SearchResult],
        answer: str,
    ) -> HostCompletion:
        """Return exact-evidence supplements for the narrowly contracted facts.

        This runs only after the one permitted model repair has failed.  Every
        fragment is checked again by :meth:`assess` by the caller.
        """
        context_list = tuple(contexts)
        assessment = self.assess(requirements, context_list, answer)
        if not assessment.applicable or not assessment.missing_fact_keys or not assessment.evidence_contract_valid:
            return HostCompletion(
                assessment.applicable, (), assessment.missing_fact_keys, (), "",
            )

        missing = set(assessment.missing_fact_keys)
        completed: list[str] = []
        cited: list[str] = []
        fragments: list[str] = []

        risk_keys = {
            "risk_history_before_grade", "risk_history_after_grade", "risk_history_reason",
        }
        if missing & risk_keys:
            row = self._latest_risk_history_row(context_list)
            if row is not None:
                date, before, after, reason, chunk_id = row
                if "risk_history_before_grade" in missing:
                    fragments.append(f"변경 이력의 {date} 기록에서 변경 전 위험등급은 {before}입니다.")
                    completed.append("risk_history_before_grade")
                if "risk_history_after_grade" in missing:
                    fragments.append(f"같은 기록의 변경 후 위험등급은 {after}입니다.")
                    completed.append("risk_history_after_grade")
                if "risk_history_reason" in missing:
                    fragments.append(f"같은 기록의 변경 사유는 {reason}입니다.")
                    completed.append("risk_history_reason")
                cited.append(chunk_id)

        irp_keys = {
            "irp_tax_deferral", "irp_tax_at_pension_receipt", "irp_tax_payment_distributed",
        }
        if missing & irp_keys:
            support = self._supporting_contexts(
                context_list,
                ("연금 수령 시까지 과세이연", "운용 중 세금 없음", "세금납부시점", "연금 수령시마다 분산"),
            )
            if support:
                if "irp_tax_deferral" in missing:
                    fragments.append("운용수익은 연금 수령 시까지 과세이연되어 운용 중 세금이 없습니다.")
                    completed.append("irp_tax_deferral")
                if "irp_tax_at_pension_receipt" in missing:
                    fragments.append("운용수익에 대한 과세는 연금 수령 시점에 이루어집니다.")
                    completed.append("irp_tax_at_pension_receipt")
                if "irp_tax_payment_distributed" in missing:
                    fragments.append("세금 납부는 연금 수령 시마다 분산됩니다.")
                    completed.append("irp_tax_payment_distributed")
                cited.extend(context.chunk_id for context in support)

        isa_keys = {
            "isa_transfer_additional_credit_rate", "isa_transfer_additional_credit_cap",
        }
        if missing & isa_keys:
            rate_support = self._supporting_contexts(context_list, ("10%",))
            cap_support = self._supporting_contexts(context_list, ("300만원",))
            if "isa_transfer_additional_credit_rate" in missing and rate_support:
                fragments.append("ISA 만기자금의 연금계좌 전환금액에는 10%의 추가 세액공제가 적용됩니다.")
                completed.append("isa_transfer_additional_credit_rate")
                cited.extend(context.chunk_id for context in rate_support)
            if "isa_transfer_additional_credit_cap" in missing and cap_support:
                fragments.append("추가 세액공제 한도는 300만원입니다.")
                completed.append("isa_transfer_additional_credit_cap")
                cited.extend(context.chunk_id for context in cap_support)

        dc_benefit_keys = {"dc_benefit_contribution", "dc_benefit_investment_return"}
        if missing & dc_benefit_keys:
            support = self._supporting_contexts(context_list, ("부담금 누계액", "운용손익"))
            if support:
                if "dc_benefit_contribution" in missing:
                    fragments.append("DC형 퇴직급여 산정에는 사용자 부담금 누계액이 반영됩니다.")
                    completed.append("dc_benefit_contribution")
                if "dc_benefit_investment_return" in missing:
                    fragments.append("운용손익도 함께 반영됩니다.")
                    completed.append("dc_benefit_investment_return")
                cited.extend(context.chunk_id for context in support)

        pension_savings_keys = {"pension_savings_early_withdrawal_compelling_reason"}
        if missing & pension_savings_keys:
            support = self._supporting_contexts(context_list, ("부득이한 사유",))
            if support:
                fragments.append("연금저축의 연금수령 전 인출은 부득이한 사유와 구분해 확인해야 합니다.")
                completed.append("pension_savings_early_withdrawal_compelling_reason")
                cited.extend(context.chunk_id for context in support)

        irp_early_withdrawal_keys = {"irp_early_withdrawal_legal_grounds"}
        if missing & irp_early_withdrawal_keys:
            support = self._supporting_contexts(context_list, ("중도인출 사유를 법으로 열거",))
            if support:
                fragments.append("IRP의 연금수령 전 중도인출은 법으로 열거된 법정사유에 해당할 때만 가능합니다.")
                completed.append("irp_early_withdrawal_legal_grounds")
                cited.extend(context.chunk_id for context in support)

        dc_early_withdrawal_document_keys = {"dc_early_withdrawal_document_requirement"}
        if missing & dc_early_withdrawal_document_keys:
            support = self._supporting_contexts(context_list, ("증빙서류",))
            if support:
                fragments.append("DC 중도인출은 법정사유별로 필요한 증빙서류를 준비해야 합니다.")
                completed.append("dc_early_withdrawal_document_requirement")
                cited.extend(context.chunk_id for context in support)

        pension_tax_keys = {
            "pension_account_investment_income_deferral", "pension_account_investment_income_not_exempt",
        }
        if missing & pension_tax_keys:
            if "pension_account_investment_income_deferral" in missing:
                support = self._supporting_contexts(context_list, ("과세이연",))
                if support:
                    fragments.append("연금계좌 운용수익은 과세이연으로 운용 중 세금 납부를 미룹니다.")
                    completed.append("pension_account_investment_income_deferral")
                    cited.extend(context.chunk_id for context in support)
            if "pension_account_investment_income_not_exempt" in missing:
                support = self._supporting_contexts(context_list, ("연금수령 시 연금소득",))
                if support:
                    fragments.append("이는 면세가 아니라 연금수령 시 연금소득으로 과세되는 구조입니다.")
                    completed.append("pension_account_investment_income_not_exempt")
                    cited.extend(context.chunk_id for context in support)

        unresolved = tuple(key for key in assessment.missing_fact_keys if key not in completed)
        return HostCompletion(
            True,
            tuple(completed),
            unresolved,
            tuple(dict.fromkeys(cited)),
            "\n".join(fragments),
        )
