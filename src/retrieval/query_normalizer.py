"""Limited, evidence-backed query token expansion for pension retrieval."""

from __future__ import annotations

import unicodedata
from typing import Iterable, Protocol, Sequence


class TokenizerProtocol(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


class QueryNormalizerProtocol(Protocol):
    def expand(self, query: str, tokenizer: TokenizerProtocol) -> list[str]: ...


def deduplicate_preserving_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class PensionQueryNormalizer:
    """Preserve original tokens and append only explicit document terminology."""

    def __init__(
        self,
        phrase_aliases: dict[str, Sequence[str]],
        token_aliases: dict[str, Sequence[str]],
    ) -> None:
        self.phrase_aliases = phrase_aliases
        self.token_aliases = token_aliases

    def expand(self, query: str, tokenizer: TokenizerProtocol) -> list[str]:
        normalized_query = unicodedata.normalize("NFC", query).lower()
        base_tokens = tokenizer.tokenize(query)
        expanded_tokens = list(base_tokens)
        for phrase, aliases in self.phrase_aliases.items():
            if phrase.lower() in normalized_query:
                for alias in aliases:
                    expanded_tokens.extend(tokenizer.tokenize(alias))
        for token in base_tokens:
            for alias in self.token_aliases.get(token.lower(), ()):
                expanded_tokens.extend(tokenizer.tokenize(alias))
        return deduplicate_preserving_order(expanded_tokens)


# Each rule is limited to expressions observed in the dev failure analysis.
DEFAULT_NORMALIZATION_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("개인부담금", ("본인 부담금",), "R-007"),
    ("세액공제", ("세액 공제 혜택",), "R-008"),
    ("세금상 불이익", ("연금외수령", "기타소득세"), "R-010"),
    ("세액공제 대상", ("종합소득", "세액공제 납입한도"), "R-012"),
    ("다른 금융회사로 이전", ("사업자이전", "계약이전"), "R-014"),
    ("퇴직연금 제도 변경", ("퇴직급여 제도 변경", "퇴직연금규약"), "R-017"),
    ("연금으로 수령", ("수급요건", "연금 지급기간"), "R-022"),
)


def build_default_pension_query_normalizer() -> PensionQueryNormalizer:
    return PensionQueryNormalizer(
        phrase_aliases={phrase: aliases for phrase, aliases, _ in DEFAULT_NORMALIZATION_RULES},
        token_aliases={},
    )
