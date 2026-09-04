"""Dedicated HCX-007 Structured Outputs caller for offline augmentation.

This caller is intentionally independent of the final-answer generator. It
does not retrieve evidence, decide outcomes, or construct provenance.
"""
from __future__ import annotations

import json
import time
import urllib.error

from src.augmentation.candidate_schema import GeneratedAugmentationText
from src.generation.errors import GenerationError
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


AUGMENTATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "coverage_tags": {"type": "array", "items": {"type": "string"}},
        "augmentation_type": {"type": "string"},
    },
    "required": ["question", "answer", "coverage_tags", "augmentation_type"],
}


class HCXStructuredAugmentationGenerator:
    """HCX-007-only native structured caller; no final Agent dependency."""

    def __init__(self, *, config, transport=None, rate_limiter=None, sleeper=time.sleep):
        if config.hcx_model.upper() != "HCX-007":
            raise ValueError("P49 augmentation Structured Outputs requires HCX-007")
        self.config = config
        self.transport = transport or UrllibTransport()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(
            config.hcx_min_interval_seconds, guard_seconds=config.hcx_pacing_guard_seconds
        )
        self.sleeper = sleeper

    def payload(self, prompt: str, response_schema: dict | None = None) -> dict:
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 1200,
            # The configured HCX-007 endpoint rejects responseFormat when this
            # explicit non-reasoning setting is omitted. ``effort=none`` does
            # not request a Thinking response and matches the existing stable
            # HCX-007 Structured Output integration in this repository.
            "thinking": {"effort": "none"},
            "responseFormat": {"type": "json", "schema": response_schema or AUGMENTATION_RESPONSE_SCHEMA},
        }

    @staticmethod
    def _content(body: str) -> str:
        data = json.loads(body)
        result = data.get("result", {}) if isinstance(data, dict) else {}
        content = result.get("message", {}).get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("HCX augmentation response has no message content")
        if content.strip().startswith("```"):
            return content.strip().split("\n", 1)[1].rsplit("```", 1)[0]
        return content

    def generate_structured(self, prompt: str, response_schema: dict | None = None) -> dict:
        """Return only model-owned structured fields for an augmentation lane."""
        payload = self.payload(prompt, response_schema)
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        diagnostics = []
        for attempt in range(self.config.max_retries + 1):
            diagnostic = {"attempt": attempt + 1, "request_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))}
            try:
                diagnostic["rate_limit_wait_ms"] = round(self.rate_limiter.acquire() * 1000, 3)
                try:
                    status, body = self.transport.post(self.config.hcx_base_url, headers, payload, self.config.timeout_seconds)
                except urllib.error.HTTPError as error:
                    status, body = error.code, error.read().decode(errors="replace")
                diagnostic["http_status"] = status
                if status == 429 or status >= 500:
                    diagnostics.append({**diagnostic, "outcome": "retry" if attempt < self.config.max_retries else "failed"})
                    if attempt < self.config.max_retries:
                        self.sleeper(0.1 * (attempt + 1))
                        continue
                    raise GenerationError("HCX augmentation unavailable", diagnostic={"attempts": diagnostics})
                if status >= 400:
                    raise GenerationError("HCX augmentation request failed", diagnostic={"attempts": diagnostics + [{**diagnostic, "outcome": "failed"}]})
                parsed = json.loads(self._content(body))
                if not isinstance(parsed, dict):
                    raise ValueError("structured augmentation response must be an object")
                return parsed
            except GenerationError:
                raise
            except Exception as exc:
                diagnostics.append({**diagnostic, "exception_type": type(exc).__name__, "outcome": "failed"})
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX augmentation response invalid", diagnostic={"attempts": diagnostics}) from exc

    def generate(self, prompt: str) -> GeneratedAugmentationText:
        return GeneratedAugmentationText.from_mapping(self.generate_structured(prompt))
