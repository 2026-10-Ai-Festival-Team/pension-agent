"""Deterministic product-name to product-code resolution.

The resolver is deliberately a closed catalog.  It never guesses a code from
similar names and returns no match for ambiguous aliases.  This lets product
field slots retain the existing ``product_code + field + value`` evidence
boundary.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Tuple


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = ROOT / "data/product_aliases_v1.json"


def _normalise(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()


@dataclass(frozen=True)
class ProductIdentity:
    code: str
    canonical_name: str
    aliases: tuple[str, ...]


class ProductEntityResolver:
    def __init__(self, catalog_path: Path = DEFAULT_CATALOG_PATH):
        self.catalog_path = catalog_path
        self._catalog = self._load(catalog_path)

    @staticmethod
    @lru_cache(maxsize=4)
    def _load(path: Path) -> Tuple[ProductIdentity, ...]:
        if not path.exists():
            return ()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return tuple(
            ProductIdentity(
                code=item["product_code"].upper(),
                canonical_name=item["canonical_name"],
                aliases=tuple(item["aliases"]),
            )
            for item in raw["products"]
        )

    def resolve(self, question: str) -> list[ProductIdentity]:
        normalized_question = _normalise(question)
        matches: list[ProductIdentity] = []
        for product in self._catalog:
            aliases = {_normalise(product.canonical_name), *(_normalise(alias) for alias in product.aliases)}
            # One- or two-character aliases are too broad to be safe product
            # identifiers in Korean text.
            if any(len(alias) >= 3 and alias in normalized_question for alias in aliases):
                matches.append(product)
        return matches
