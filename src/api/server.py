"""Environment-validated ASGI composition root for local deployment."""
from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from src.api.main import create_local_app


def build_application():
    load_dotenv()
    corpus = Path(os.getenv("CORPUS_PATH", os.getenv("PARSED_DATA_ROOT", "data/parsed") + "/chunks.jsonl"))
    index = Path(os.getenv("BM25_INDEX_PATH", os.getenv("INDEX_DATA_ROOT", "data/indexes") + "/bm25/simple"))
    missing = [str(path) for path in (corpus, index / "index_meta.json") if not path.exists()]
    if missing:
        raise RuntimeError("Required corpus or BM25 index is missing: " + ", ".join(missing))
    backend = os.getenv("GENERATOR_BACKEND", "fake")
    environment = os.getenv("APP_ENV", "development")
    if environment in {"evaluation", "production"} and backend != "hcx":
        raise RuntimeError("HCX generator is required in evaluation mode.")
    if backend != "fake":
        raise RuntimeError("Configured generator backend is not available in this deployment branch.")
    return create_local_app(corpus, index)

