"""Common parser call contract."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.models.document import ParsedDocument


class DocumentParser(Protocol):
    supported_extensions: set[str]

    def parse(self, path: Path, source_root: Path) -> ParsedDocument:
        """Return a location-preserving, schema-valid document representation."""
