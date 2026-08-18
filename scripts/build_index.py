from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import get_settings
from src.ingestion.chunker import chunk_document
from src.ingestion.loader import discover_documents, load_document
from src.ingestion.parser import normalize_document
from src.retrieval.bm25_retriever import save_chunks


def main() -> int:
    settings = get_settings()
    paths = discover_documents(settings.raw_data_dir)
    if not paths:
        print("대회 원본 자료가 없어 index를 만들지 않았습니다. data/raw에 자료를 추가하세요.")
        return 2
    chunks = []
    for path in paths:
        chunks.extend(chunk_document(normalize_document(load_document(path, settings.raw_data_dir))))
    save_chunks(chunks, settings.index_path)
    print(f"documents={len(paths)} chunks={len(chunks)} index={settings.index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
