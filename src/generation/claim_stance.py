"""Deterministic stance handling for narrow, evidence-backed confirmation questions.

This is deliberately not a general natural-language inference layer.  It only
acts when a selected canonical requirement itself fixes the requested party
and the question explicitly asserts either the company or the participant as
the operator.  All other questions stay ``neutral`` and are left to the
normal evidence-grounded writer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from src.orchestration.confirmation_normalizer import normalize_confirmation_query


_OPERATION_PARTY = {
    "DB.operation_party": ("회사", "DB형 적립금 운용 주체는 회사입니다."),
    "DC.operation_party": ("근로자", "DC형 적립금 운용 주체는 근로자입니다."),
}
_LEADING_POLARITY = re.compile(
    r"^\s*(?:네|예|아니요|아뇨)(?:\s*[,，]?\s*(?:맞습니다|맞아요|그렇습니다|그렇죠|맞죠|아닙니다|아니에요|그렇지\s*않습니다|그렇지\s*않아요))?[\s.!…]*",
)


@dataclass(frozen=True)
class ClaimStance:
    """A writer contract derived only from a selected direct requirement."""

    stance: str = "neutral"  # support | contradict | neutral
    user_claim: str | None = None
    supported_fact: str | None = None
    query_modality: str = "neutral"
    normalized_claim: str | None = None
    claim_polarity: str | None = None
    stance_reason: str | None = None

    @property
    def answer_prefix(self) -> str | None:
        if self.stance == "support":
            return "네."
        if self.stance == "contradict":
            return "아니요."
        return None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "stance": self.stance,
            "user_claim": self.user_claim,
            "supported_fact": self.supported_fact,
            "query_modality": self.query_modality,
            "normalized_claim": self.normalized_claim,
            "claim_polarity": self.claim_polarity,
            "stance_reason": self.stance_reason,
        }

    def writer_instruction(self) -> str:
        if self.stance == "neutral":
            return ""
        return (
            "\n\n[Confirmation stance contract]\n"
            f"- User claim: {self.user_claim}\n"
            f"- Directly supported fact: {self.supported_fact}\n"
            f"- Stance: {self.stance}\n"
            f"- The first sentence MUST begin with `{self.answer_prefix}`. "
            "Do not agree with the user claim when the stance is contradict."
        )

    def apply_answer_prefix(self, answer: str) -> str:
        """Make an explicit confirmation token deterministic after generation.

        We never change the factual body of a generated answer.  This only
        prevents a habitual leading ``네`` from contradicting the direct fact
        that the same response subsequently states.
        """
        if not self.answer_prefix:
            return answer
        body = _LEADING_POLARITY.sub("", answer).strip()
        return self.answer_prefix if not body else f"{self.answer_prefix} {body}"


def resolve_claim_stance(question: str, requirements: tuple[str, ...]) -> ClaimStance:
    """Resolve an explicit DB/DC operation-party confirmation conservatively.

    A question such as ``누가 운용하나요`` is factual but does not assert a
    proposition, so it remains neutral.  Negated wording is likewise left
    neutral rather than riskfully reversing the user's claim.
    """
    normalization = normalize_confirmation_query(question)
    operation_requirements = [key for key in requirements if key in _OPERATION_PARTY]
    if len(operation_requirements) != 1:
        return ClaimStance(query_modality=normalization.query_modality)

    normalized = re.sub(r"\s+", "", question)
    core = re.sub(r"\s+", "", normalization.proposition_core)
    if "누가" in core or not any(token in core for token in ("운용", "굴리", "관리", "맡")):
        return ClaimStance(query_modality=normalization.query_modality)

    asserted_party = None
    if any(token in core for token in ("회사", "사업주", "사용자")):
        asserted_party = "회사"
    elif any(token in core for token in ("내가", "제가", "근로자", "가입자", "직접")):
        asserted_party = "근로자"
    if asserted_party is None:
        return ClaimStance(query_modality=normalization.query_modality)

    supported_party, supported_fact = _OPERATION_PARTY[operation_requirements[0]]
    participant = r"(?:내가|제가|근로자(?:가|는)?|가입자(?:가|는)?|직접)"
    company = r"(?:회사(?:가|는)?|사업주(?:가|는)?|사용자(?:가|는)?)"
    party_pattern = participant if asserted_party == "근로자" else company
    # Internal negation (``내가 안 굴리는``) and a declarative
    # ``... 제도가 아니지`` negate the proposition.  Terminal ``거 아니야?``
    # is handled as an interrogative modality by the normalizer, not as scope
    # negation.
    claim_negative = bool(
        re.search(party_pattern + r".{0,16}(?:안|않).{0,8}(?:운용|굴리|관리|맡)", normalized)
        or re.search(party_pattern + r".{0,24}(?:운용|굴리|관리|맡).{0,12}(?:제도|방식).{0,4}아니", normalized)
    )
    claim_polarity = "negative" if claim_negative else "positive"
    user_claim = f"적립금 운용 주체는 {asserted_party}{'가 아닙니다' if claim_negative else '입니다'}."
    claim_matches_fact = (asserted_party == supported_party) != claim_negative
    return ClaimStance(
        stance="support" if claim_matches_fact else "contradict",
        user_claim=user_claim,
        supported_fact=supported_fact,
        query_modality=normalization.query_modality,
        normalized_claim=f"{operation_requirements[0].split('.')[0]} {asserted_party} operation",
        claim_polarity=claim_polarity,
        stance_reason=f"direct_requirement:{operation_requirements[0]} states {supported_party} operates reserves",
    )
