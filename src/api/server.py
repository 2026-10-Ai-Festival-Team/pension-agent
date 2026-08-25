"""Runnable local composition root for the browser UI and API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from src.api.main import create_browser_configured_app


ROOT = Path(__file__).resolve().parents[2]


def _resolve_from_root(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def create_server_app():
    """Load local settings once, then build the actual retrieval-backed app."""

    load_dotenv(ROOT / ".env")
    parsed_root = _resolve_from_root(os.getenv("PARSED_DATA_ROOT", "data/parsed"))
    index_root = _resolve_from_root(os.getenv("INDEX_DATA_ROOT", "data/indexes"))
    corpus_path = parsed_root / "chunks.jsonl"
    index_path = index_root / "bm25/simple"
    missing = [str(path.relative_to(ROOT)) for path in (corpus_path, index_path) if not path.exists()]
    if missing:
        raise RuntimeError(
            "검색용 생성 파일을 찾을 수 없습니다: " + ", ".join(missing)
            + ". data/parsed/chunks.jsonl과 data/indexes/bm25/simple을 준비하세요."
        )
    return create_browser_configured_app(corpus_path, index_path)


app = create_server_app()
