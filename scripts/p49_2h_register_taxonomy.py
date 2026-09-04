"""Shared host-owned wording-register policy for new P49-2H augmentation.

The legacy 4B artifacts use ``general`` and ``beginner``.  They remain valid
and reproducible.  New additive manifests use the canonical allocation cycle
below, where the two informal Korean registers make up exactly 20 percent.
Register controls wording only; they never authorize abbreviations, typos, or
semantic omission.
"""
from __future__ import annotations


CANONICAL_REGISTERS = (
    "formal",
    "polite",
    "conversational",
    "casual_banmal",
    "terse_banmal",
)

# 2 / 10 is the maximum planned informal share.  The cycle is deterministic so
# a manifest can be reproduced from its immutable source rows.
REGISTER_ALLOCATION_CYCLE = (
    "formal",
    "polite",
    "conversational",
    "formal",
    "polite",
    "conversational",
    "formal",
    "polite",
    "casual_banmal",
    "terse_banmal",
)

LEGACY_REGISTERS = ("general", "beginner")
BANMAL_REGISTERS = frozenset({"casual_banmal", "terse_banmal"})

REGISTER_RULES = {
    "formal": "격식 있는 존댓말(예: ‘-습니까?’)로 작성하되, 질문의 사실·조건·대상을 생략하지 마세요.",
    "polite": "자연스러운 해요체 존댓말(예: ‘-인가요?’, ‘-할 수 있나요?’)로 작성하세요.",
    "conversational": "전문용어를 불필요하게 늘리지 않은 자연스러운 일상 존댓말 질문으로 작성하세요.",
    "casual_banmal": (
        "자연스러운 반말 의문형(예: ‘-야?’, ‘-거야?’, ‘-맞아?’)으로 작성하세요. "
        "반말은 말투만 바꾸며 subject·수치·조건·범위를 생략하거나 속어·비하 표현을 추가하지 마세요."
    ),
    "terse_banmal": (
        "짧은 반말 의문형(예: ‘-임?’, ‘-맞지?’, ‘-몰라?’)으로 작성하세요. "
        "짧아도 subject·target·필요 조건이 분명해야 하며, 줄임말·오타·조사 탈락을 임의로 넣지 마세요."
    ),
    # Backward-compatible values for immutable 4B/v4/v5/v6 artifacts.
    "general": "일반적인 금융 이용자가 이해할 수 있는 중립적이고 자연스러운 표현을 사용하세요.",
    "beginner": "초보자가 실제로 말할 법한 쉬운 표현을 쓰되, subject와 target은 흐리지 마세요.",
}


def register_for_index(index: int) -> str:
    """Return the deterministic new-manifest register for a zero-based index."""
    if index < 0:
        raise ValueError("register allocation index must be non-negative")
    return REGISTER_ALLOCATION_CYCLE[index % len(REGISTER_ALLOCATION_CYCLE)]


def is_valid_register(value: str) -> bool:
    return value in REGISTER_RULES
