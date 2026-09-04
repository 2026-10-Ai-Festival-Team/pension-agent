"""Canonicalise bounded Korean pension-question expressions.

This is intentionally a semantic front-end, not a question-ID router.  Each
normalisation maps a reusable surface family to a concept already supported by
the requirement schemas.  The original user question remains available to the
caller; this canonical form is used only for extraction and planning.
"""
from __future__ import annotations

import re


_SPACE_NORMALISATIONS = (
    (re.compile(r"연금\s+저축"), "연금저축"),
    (re.compile(r"일반\s+계좌"), "일반계좌"),
    (re.compile(r"세액\s+공제"), "세액공제"),
)
_PENSION_SAVINGS_ALIAS = re.compile(r"연\s*저(?:\s*계좌)?")
_PENSION_SAVINGS_DESCRIPTIVE_ALIAS = re.compile(r"개인\s*연금\s*저축(?:\s*계좌)?")
_IRP_DESCRIPTIVE_ALIAS = re.compile(r"개인형\s*퇴직\s*연금")
_MID_WITHDRAWAL = re.compile(
    r"(?:중간|도중)(?:에)?\s*(?:돈(?:을|을?\s*)?)?\s*(?:찾|꺼내|빼)(?:기|려|려고|면|는|기\s*전)?"
)
_PRE_RETIREMENT_WITHDRAWAL = re.compile(
    r"(?:(?:퇴직|퇴사)(?:하기)?\s*전(?:에)?|재직\s*중)(?:\s*적립금)?(?:\s*일부(?:를)?)?\s*(?:돈(?:을)?\s*)?(?:찾|찾을|꺼내|꺼낼|빼|뺄)(?:기|려|려고|면|는|수)?"
)
_PROOF_DOCUMENT = re.compile(r"증명\s*(?:서류|자료)")
_SUBMITTING_EVIDENCE = re.compile(r"(?:어떤|무슨)?\s*근거(?:를)?\s*내")
_TAX_DEFERRAL = re.compile(
    r"세금(?:을|이)?\s*(?:나중|뒤|추후)(?:에)?\s*(?:내|납부)[가-힣]*"
)
# ``넘기다`` conjugates to both ``넘길`` and ``넘겨``.  Treat it as a
# transfer operation only inside the ISA-maturity guard below.
_TRANSFER = re.compile(r"넘(?:기|겨|길)[가-힣]*")
_OPERATION_PARTY = re.compile(r"(?:돈|적립금)(?:을)?\s*굴려(?:주는)?\s*(?:쪽|주체|사람)?")
_FIXED_GRADE = re.compile(r"(?:계속|항상)\s*(?:고정|그대로)")
_ISA_END = re.compile(r"ISA\s*(?:가)?\s*(?:끝난\s*뒤|끝난\s*후|종료\s*후)", re.IGNORECASE)
_ETF_LEVERAGE = re.compile(r"(?:두\s*배|배수)(?:로)?\s*(?:움직이|추종)")
_ETF_INVERSE = re.compile(r"(?:반대(?:로|\s*방향(?:으로)?)?|하락)\s*(?:움직이|추종)")
_ETF_LEVERAGE_INVERSE = re.compile(r"상승\s*[·ㆍ/]?\s*하락\s*배수(?:를)?\s*추종")
_IN_KIND_TRANSFER = re.compile(
    r"(?:환매|매도)\s*하지\s*않(?:고|은)(?:\s*채)?\s*(?:퇴직연금\s*)?(?:사업자|금융회사|기관)(?:만)?\s*(?:바꾸|변경)"
)
_RISK_CLASSIFICATION = re.compile(r"투자\s*위험\s*분류|몇\s*단계\s*위험")
_RISK_CHANGE = re.compile(r"(?:나중에\s*)?(?:다시\s*)?조정될\s*수(?:도)?\s*(?:있|없)|계속\s*(?:고정|그대로)")
_INDEX_TRACKING = re.compile(r"특정\s*지수\s*성과(?:를)?\s*(?:반영|따르|추종)|지수\s*성과(?:를)?\s*(?:반영|따르|추종)")
_EQUITY_ALLOCATION = re.compile(r"주식\s*관련\s*자산\s*편입\s*비율")
_HELD_COST_EXAMPLE = re.compile(r"\d+\s*년\s*보유(?:를)?\s*가정(?:한)?\s*비용(?:\s*금액)?")


def normalize_pension_question(question: str) -> str:
    """Return a canonical planning form while preserving the user's wording elsewhere.

    Context guards keep broad Korean verbs from acquiring a pension meaning:
    ``넘기다`` becomes a transfer operation only for an ISA-maturity question,
    and ``고정`` becomes a risk-grade-changeability request only when a grade
    is already being discussed.
    """
    canonical = question.strip()
    for pattern, replacement in _SPACE_NORMALISATIONS:
        canonical = pattern.sub(replacement, canonical)
    canonical = _PENSION_SAVINGS_ALIAS.sub("연금저축", canonical)
    canonical = _PENSION_SAVINGS_DESCRIPTIVE_ALIAS.sub("연금저축", canonical)
    canonical = _IRP_DESCRIPTIVE_ALIAS.sub("IRP", canonical)
    canonical = _MID_WITHDRAWAL.sub("중도인출", canonical)
    canonical = _PRE_RETIREMENT_WITHDRAWAL.sub("중도인출", canonical)
    canonical = _PROOF_DOCUMENT.sub("증빙서류", canonical)
    if "중도인출" in canonical:
        canonical = _SUBMITTING_EVIDENCE.sub("증빙서류", canonical)
    canonical = _TAX_DEFERRAL.sub("과세이연", canonical)
    canonical = _ISA_END.sub("ISA 만기", canonical)
    canonical = _ETF_LEVERAGE_INVERSE.sub("레버리지 인버스", canonical)
    canonical = _ETF_LEVERAGE.sub("레버리지", canonical)
    canonical = _ETF_INVERSE.sub("인버스", canonical)
    canonical = _IN_KIND_TRANSFER.sub("실물이전", canonical)
    canonical = _RISK_CLASSIFICATION.sub("위험등급", canonical)
    canonical = _INDEX_TRACKING.sub("지수 추종", canonical)
    canonical = _EQUITY_ALLOCATION.sub("주식 투자 비중", canonical)
    canonical = _HELD_COST_EXAMPLE.sub("기간별 비용 예시", canonical)
    if "가입자" in canonical and "교육" in canonical:
        canonical = canonical.replace("책임지고 시행", "교육 실시 주체")
        canonical = canonical.replace("1년에", "매년 1회")
        canonical = canonical.replace("전문기관에 위임", "교육 위탁")
    if "ETF" in canonical.upper() and "해외" in canonical and "계좌 밖" in canonical:
        canonical = canonical.replace("계좌 밖", "일반계좌")
    if "ISA" in canonical.upper() and "만기" in canonical:
        canonical = _TRANSFER.sub("이전", canonical)
    if {"DB", "DC"} <= {item.upper() for item in re.findall(r"(?<![A-Za-z])(?:DB|DC)(?![A-Za-z])", canonical)}:
        canonical = _OPERATION_PARTY.sub("적립금 운용 주체", canonical)
    if "등급" in canonical:
        canonical = _FIXED_GRADE.sub("등급이 고정", canonical)
        canonical = _RISK_CHANGE.sub("위험등급 변경될 수", canonical)
    return canonical
