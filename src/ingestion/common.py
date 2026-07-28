"""Format-independent helpers for source identity and conservative metadata extraction."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


PRODUCT_CODE_PATTERN = re.compile(r"(?<![A-Z0-9])KR[A-Z0-9]{10}(?![A-Z0-9])")
DATE_PATTERNS = [
    re.compile(r"\b20\d{2}[.-]\d{1,2}[.-]\d{1,2}\b"),
    re.compile(r"\b20\d{2}년\s*\d{1,2}월\s*\d{1,2}일\b"),
    re.compile(r"\b20\d{2}[.-]\d{1,2}\b"),
    re.compile(r"\b20\d{2}년\s*\d{1,2}월\b"),
]


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def normalize_text(value: str) -> str:
    normalized = normalize_unicode(value)
    lines = [" ".join(line.split()) for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def make_source_id(relative_path_value: str) -> str:
    normalized = normalize_unicode(relative_path_value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def extract_product_codes(*values: str) -> list[str]:
    found: set[str] = set()
    for value in values:
        found.update(PRODUCT_CODE_PATTERN.findall(normalize_unicode(value)))
    return sorted(found)


def extract_date_candidates(text: str) -> list[str]:
    found: set[str] = set()
    normalized = normalize_unicode(text)
    for pattern in DATE_PATTERNS:
        found.update(pattern.findall(normalized))
    return sorted(found)


def relative_path(path: Path, source_root: Path) -> str:
    return normalize_unicode(path.relative_to(source_root).as_posix())
