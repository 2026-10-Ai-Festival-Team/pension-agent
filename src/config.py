from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    raw_data_dir: Path = ROOT_DIR / "data" / "raw"
    processed_data_dir: Path = ROOT_DIR / "data" / "processed"
    index_path: Path = ROOT_DIR / "data" / "processed" / "chunks.jsonl"
    hcx_api_key: str = os.getenv("HCX_API_KEY", "")
    hcx_request_id: str = os.getenv("HCX_REQUEST_ID", "")
    hcx_endpoint: str = os.getenv(
        "HCX_ENDPOINT", "https://clovastudio.stream.ntruss.com"
    ).rstrip("/")
    hcx_model: str = os.getenv("HCX_MODEL", "HCX-DASH-002")
    hcx_timeout_seconds: float = float(os.getenv("HCX_TIMEOUT_SECONDS", "30"))
    hcx_max_retries: int = int(os.getenv("HCX_MAX_RETRIES", "2"))
    max_question_length: int = int(os.getenv("MAX_QUESTION_LENGTH", "2000"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "5"))


def get_settings() -> Settings:
    return Settings()
