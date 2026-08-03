"""Conservatively extract searchable row labels from rendered table chunks."""

from __future__ import annotations

import re

from src.models.chunk import ChunkType, SearchChunk


def row_keys(chunk: SearchChunk) -> list[str]:
    """Return one de-duplicated key per data row; never index non-table chunks."""
    if chunk.chunk_type != ChunkType.TABLE:
        return []
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]
    if not lines:
        return []
    keys: list[str] = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.split("|")]
        first = next((cell for cell in cells if cell), "")
        if not first or index == 0:  # first nonempty line is the rendered header
            continue
        first = re.sub(r"^\d+[.)]\s*", "", first)
        if first and first not in keys:
            keys.append(first)
    return keys
