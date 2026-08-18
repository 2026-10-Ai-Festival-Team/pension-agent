from __future__ import annotations

import re

from src.ingestion.loader import LoadedDocument


def normalize_document(document: LoadedDocument) -> LoadedDocument:
    for page in document.pages:
        page.text = re.sub(r"[ \t]+", " ", page.text.replace("\x00", ""))
        page.text = re.sub(r"\n{3,}", "\n\n", page.text).strip()
        lines = [line for line in page.text.splitlines() if line.strip()]
        if document.contains_table and lines:
            malformed = sum(line.count("|") == 0 for line in lines) / len(lines) > 0.7
            page.metadata["possible_table_parse_issue"] = malformed
    return document
