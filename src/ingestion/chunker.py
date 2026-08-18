from __future__ import annotations

import hashlib
import re

from src.ingestion.loader import LoadedDocument
from src.schemas.models import DocumentChunk


HEADING = re.compile(r"^(?:#{1,6}\s+|\d+(?:[.-]\d+)*[.)]?\s+|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[.)]?\s*)")


def _semantic_blocks(text: str) -> list[str]:
    """Keep paragraphs/tables intact and avoid treating every PDF line as a section."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) <= 1:
        return [text.strip()] if text.strip() else []
    blocks: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        if HEADING.match(paragraph) and current:
            blocks.append("\n\n".join(current))
            current = []
        current.append(paragraph)
    if current:
        blocks.append("\n\n".join(current))
    return blocks


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundaries = (text.rfind("\n\n", start, end), text.rfind("\n", start, end), text.rfind(". ", start, end))
            boundary = max(boundaries)
            if boundary > start + max_chars // 2:
                end = boundary + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [part for part in parts if part]


def chunk_document(document: LoadedDocument, max_chars: int = 1200, overlap: int = 120) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for page in document.pages:
        for section in _semantic_blocks(page.text):
            for text in _split_long(section, max_chars, overlap):
                if len(re.findall(r"[가-힣A-Za-z0-9]", text)) < 10:
                    continue
                ordinal = len(chunks) + 1
                digest = hashlib.sha1(f"{document.document_id}:{page.page}:{ordinal}:{text}".encode()).hexdigest()[:10]
                chunks.append(DocumentChunk(chunk_id=f"CHK-{digest.upper()}", document_id=document.document_id, file_name=document.path.name, page=page.page, text=text, metadata=dict(page.metadata)))
    return chunks
