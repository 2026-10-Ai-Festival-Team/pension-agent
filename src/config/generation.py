"""생성 백엔드의 환경 설정을 검증한다."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationSettings:
    environment: str = "development"
    generator_backend: str = "fake"
    hcx_api_key: str = ""
    hcx_model: str = ""
    hcx_base_url: str = ""
    timeout_seconds: float = 30
    max_retries: int = 2
    hcx_min_interval_seconds: float = 2.0
    hcx_pacing_guard_seconds: float = 0.1

    @classmethod
    def from_env(cls) -> "GenerationSettings":
        value = cls(
            environment=os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")),
            generator_backend=os.getenv("GENERATOR_BACKEND", "fake"),
            hcx_api_key=os.getenv("HCX_API_KEY", ""),
            hcx_model=os.getenv("HCX_MODEL", ""),
            hcx_base_url=os.getenv("HCX_BASE_URL", os.getenv("HCX_API_URL", "")),
            timeout_seconds=float(os.getenv("HCX_TIMEOUT_SECONDS", "30")),
            max_retries=int(os.getenv("HCX_MAX_RETRIES", "2")),
            hcx_min_interval_seconds=float(os.getenv("HCX_MIN_INTERVAL_SECONDS", "2")),
            hcx_pacing_guard_seconds=float(os.getenv("HCX_PACING_GUARD_SECONDS", "0.1")),
        )
        if value.environment in {"production", "evaluation"} and value.generator_backend != "hcx":
            raise RuntimeError("HCX generator is required in evaluation mode.")
        return value
