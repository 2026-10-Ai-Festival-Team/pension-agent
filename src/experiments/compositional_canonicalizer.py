"""Isolated P38-1 compositional parser for closed pension questions.

This module is deliberately *not* imported by the production candidate.  It
turns reusable semantic atoms into requirements so its behaviour can be
measured before any shadow integration is considered.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


_PRODUCT_CODE = re.compile(r"KR[A-Z0-9]{10}", re.IGNORECASE)


@dataclass(frozen=True)
class SemanticAtoms:
    """Canonical, order-independent semantic atoms for one question."""

    subjects: tuple[str, ...]
    actions: tuple[str, ...]
    fields: tuple[str, ...]
    modifiers: tuple[str, ...]


def _ordered(values: set[str]) -> tuple[str, ...]:
    return tuple(sorted(values))


class CompositionalParser:
    """Extract subject, action, field, and condition atoms independently.

    The patterns below are atom-level Korean constructions (e.g. a withdrawal
    verb or an evidence-document noun), rather than question-ID or full-
    sentence routes.  Clear names and abbreviations are lexical; the parser
    composes their meaning only after all atom classes are extracted.
    """

    _ACCOUNT_PATTERNS = (
        ("account:DB", re.compile(r"(?<![A-Za-z])DB(?![A-Za-z])|확정급여형")),
        ("account:DC", re.compile(r"(?<![A-Za-z])DC(?![A-Za-z])|확정기여형")),
        ("account:IRP", re.compile(r"(?<![A-Za-z])IRP(?![A-Za-z])|개인형\s*퇴직\s*연금")),
        ("account:pension_savings", re.compile(r"연금\s*저축|개인(?:용)?\s*연금\s*저축")),
        ("account:general", re.compile(r"일반\s*(?:계좌|투자계좌)|통상\s*계좌|계좌\s*밖")),
        ("account:pension", re.compile(r"연금계좌")),
        ("account:ISA", re.compile(r"(?<![A-Za-z])ISA(?![A-Za-z])")),
    )

    _ACTION_PATTERNS = (
        ("contribute", re.compile(r"(?<!전환)납입|보탠|연금\s*저축.*활용")),
        ("withdraw", re.compile(r"인출|꺼내|찾(?:을|는|기)|빼(?:려|면|는|기)|사용")),
        ("transfer", re.compile(r"이전|전환\s*납입|넘기|옮기|(?:금융기관|사업자).*변경|바꾸")),
        ("receive", re.compile(r"(?:운용\s*)?(?:수익|이익).*(?:세금|과세)|(?:세금|과세).*(?:운용\s*)?(?:수익|이익)")),
        ("manage", re.compile(r"운용\s*(?:결정|주체|방법)|(?:적립금|자산).*(?:관리|굴리|운용)|(?:관리|굴리|운용).*(?:적립금|자산)")),
        ("invest", re.compile(r"ETF|지수|주식(?:성)?\s*자산")),
        ("compare", re.compile(r"비교|차이|나란히|달라지|다른가|같은가|두\s*계좌|더\s*(?:낮|높)|DB.*DC|DC.*DB")),
        ("educate", re.compile(r"교육|안내\s*교육")),
    )

    _FIELD_PATTERNS = (
        ("operation_party", re.compile(r"운용\s*(?:결정|주체|방법)|관리\s*(?:주체|하는)|굴리|맡")),
        ("benefit_determination", re.compile(r"퇴직(?:급여|금|\s*뒤).*(?:기준|산정|계산|금액)|(?:기준|산정|계산).*(?:퇴직급여|퇴직금|퇴직\s*뒤)")),
        ("contribution_structure", re.compile(r"DC.*회사.*(?:적립|넣)|회사.*DC.*(?:적립|기준|최소)")),
        ("education_provider", re.compile(r"교육.*(?:누가|누구|책임|시행)|(?:누가|누구|책임).*교육")),
        ("education_frequency", re.compile(r"(?:최소|1년|매년|연간).*(?:몇\s*번|실시|주기)|(?:몇\s*번|실시\s*주기).*교육")),
        ("education_outsourcing", re.compile(r"교육.*(?:위임|위탁|대행|전문기관)|(?:위임|위탁|대행).*교육")),
        ("etf_direct_trade", re.compile(r"ETF.*(?:직접\s*(?:주문|거래|매매)|직접)|(?:직접\s*(?:주문|거래|매매)).*ETF")),
        ("leverage_inverse_restriction", re.compile(r"(?:두\s*배|배수|역방향|반대로|레버리지|인버스).*(?:ETF|제한|포함)|ETF.*(?:두\s*배|배수|역방향|반대로|레버리지|인버스|제한)")),
        ("tax_credit_limit", re.compile(r"(?:세액|공제).*(?:한도|상한)|(?:한도|상한).*(?:세액|공제)")),
        ("tax_timing", re.compile(r"과세\s*(?:시점|되는\s*때|언제)|세금.*(?:언제|바로|나중|사라지)|(?:언제|바로|나중).*세금")),
        ("tax_condition", re.compile(r"(?:세법|예외|조건|기준).*(?:해외\s*ETF|분배금|매매\s*이익)|(?:해외\s*ETF|분배금|매매\s*이익).*(?:세법|예외|조건|기준)")),
        ("withdrawal_reason", re.compile(r"(?:법정|허용|가능|어떤|무슨|법.*정한).*(?:사유|이유|요건)|(?:사유|이유|요건).*(?:인출|꺼내|찾|빼|사용)")),
        ("required_document", re.compile(r"(?:서류|자료|문서|입증|증빙|확인\s*문서|뭘\s*내)")),
        ("procedure", re.compile(r"절차|접수|과정")),
        ("tax_treatment", re.compile(r"(?:인출|꺼내|찾|빼).*세(?:금|율)|세(?:금|율).*(?:인출|꺼내|찾|빼)")),
        ("transfer_deadline", re.compile(r"(?:마감일|기한|언제까지|허용\s*기한)")),
        ("transfer_definition", re.compile(r"(?:매각|환매|매도)하지\s*않|실물이전|이전\s*방식")),
        ("application_route", re.compile(r"(?:신청|접수)\s*(?:경로|방식)|(?:경로|방식).*(?:신청|접수)|영업점|모바일")),
        ("risk_grade", re.compile(r"위험\s*(?:등급|분류|단계)|리스크\s*분류|안정성\s*등급|몇\s*단계|몇\s*등급")),
        ("risk_grade_changeability", re.compile(r"(?:위험|등급|분류).*(?:변경|조정|달라질|고정|그대로)|(?:변경|조정|달라질).*(?:위험|등급|분류)|(?:시장\s*여건|운용\s*(?:실적|결과)).*(?:위험|등급|분류)")),
        ("tracking_index", re.compile(r"(?:성과\s*기준.*지수|어떤\s*지수|지수.*(?:추종|반영|기준)|지수를\s*따라)")),
        ("equity_allocation_limit", re.compile(r"(?:주식(?:성)?\s*자산|주식\s*관련\s*자산).*(?:최대|상한|비율|편입)|(?:최대|상한).*(?:주식(?:성)?\s*자산|편입)")),
        ("total_fee", re.compile(r"(?:총\s*보수|연\s*단위\s*보수|보수\s*비율)")),
        ("cost_example", re.compile(r"(?:\d+\s*년|일정\s*기간).*(?:비용|금액)|(?:비용|금액).*(?:\d+\s*년|일정\s*기간)")),
    )

    _MODIFIER_PATTERNS = (
        ("before_retirement", re.compile(r"퇴직\s*전|근무\s*중|재직\s*중|55세\s*전")),
        ("combined_limit", re.compile(r"함께|같이|까지\s*(?:보탠|납입)|합산")),
        ("comparison", re.compile(r"비교|차이|나란히|달라지|다른가|같은가|두\s*계좌|더\s*(?:낮|높)")),
        ("current", re.compile(r"현재|지금")),
        ("change_possibility", re.compile(r"(?:변경|조정|달라질).*(?:가능|수|여지)|고정|그대로")),
        ("maturity_event", re.compile(r"ISA.*(?:끝|종료|만기)|(?:끝|종료|만기).*ISA")),
        ("additional_credit", re.compile(r"추가\s*세액?공제|추가.*공제")),
        ("in_kind", re.compile(r"(?:매각|환매|매도)하지\s*않|실물이전")),
        ("annual_rate", re.compile(r"매년|연\s*단위|보수\s*비율")),
        ("holding_period", re.compile(r"\d+\s*년\s*(?:보유|투자)|일정\s*기간\s*(?:투자|보유)")),
        ("field_boundary", re.compile(r"같은\s*(?:단위|방식).*않|왜.*(?:같|다르)|두\s*수치.*(?:같|다르)")),
        ("relative_low_risk", re.compile(r"(?:더|상대적(?:으로)?)\s*(?:낮은|안정)|보수적(?:으로)?\s*분류|위험.*낮")),
        ("not_tax_exempt", re.compile(r"사라지|영영\s*안")),
    )

    def parse(self, question: str) -> SemanticAtoms:
        text = self._lexically_normalize(question)
        subjects = self._subjects(text)
        actions = self._atoms(text, self._ACTION_PATTERNS)
        fields = self._atoms(text, self._FIELD_PATTERNS)
        modifiers = self._atoms(text, self._MODIFIER_PATTERNS)

        product_subjects = {subject for subject in subjects if subject.startswith("product:")}
        if product_subjects:
            actions.add("invest")
        if {"account:general", "account:pension"} <= subjects:
            actions.add("compare")
        if "ETF" in text.upper():
            actions.discard("receive")

        account_subjects = {subject for subject in subjects if subject.startswith("account:")}
        if len(account_subjects) >= 2:
            modifiers.add("account_specific")
        if "compare" in actions:
            modifiers.add("comparison")
        if "required_document" in fields and "withdraw" not in actions:
            fields.discard("required_document")
        if "procedure" in fields and "withdraw" not in actions:
            fields.discard("procedure")
        if "withdraw" not in actions:
            modifiers.discard("before_retirement")
        if "risk_grade_changeability" in fields and "risk_grade" not in fields:
            fields.discard("risk_grade_changeability")
        if "risk_grade_changeability" in fields:
            modifiers.add("change_possibility")
        elif "risk_grade" not in fields:
            modifiers.discard("change_possibility")
        if "contribute" not in actions:
            modifiers.discard("combined_limit")
        if "account:ISA" in subjects and re.search(r"(?:끝|종료|만기)", text):
            actions.add("transfer")
            actions.discard("contribute")
        if "compare" in actions and len(product_subjects) >= 2:
            actions.discard("invest")
        return SemanticAtoms(_ordered(subjects), _ordered(actions), _ordered(fields), _ordered(modifiers))

    @staticmethod
    def _lexically_normalize(question: str) -> str:
        """Only safe lexical cleanup; semantic meaning is extracted downstream."""
        text = re.sub(r"연\s+금\s+저\s+축", "연금저축", question.strip())
        text = re.sub(r"개인형\s*퇴직\s*연금", "IRP", text)
        text = re.sub(r"확정급여형", "DB", text)
        text = re.sub(r"확정기여형", "DC", text)
        return text

    @classmethod
    def _atoms(cls, text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> set[str]:
        return {name for name, pattern in patterns if pattern.search(text)}

    @classmethod
    def _subjects(cls, text: str) -> set[str]:
        subjects = {name for name, pattern in cls._ACCOUNT_PATTERNS if pattern.search(text)}
        subjects.update(f"product:{code.upper()}" for code in _PRODUCT_CODE.findall(text))
        if re.search(r"해외\s*ETF", text):
            subjects.add("product:foreign_etf")
        if "퇴직연금" in text and not subjects:
            subjects.add("system:retirement_pension")
        if "가입자" in text and "교육" in text:
            subjects.add("system:retirement_pension")
        return subjects


class RequirementComposer:
    """Compose one canonical requirement for every requested factual field."""

    @staticmethod
    def compose(atoms: SemanticAtoms) -> tuple[str, ...]:
        subject_scope = "+".join(atoms.subjects)
        action_scope = "+".join(atoms.actions)
        modifier_scope = "+".join(atoms.modifiers) if atoms.modifiers else "none"
        return tuple(
            f"{subject_scope}.{action_scope}.{field}[{modifier_scope}]"
            for field in atoms.fields
        )
