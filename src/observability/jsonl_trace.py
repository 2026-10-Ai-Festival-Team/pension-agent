"""Privacy-minimised JSONL traces for Cloud Log Analytics custom-log pickup.

The writer is deliberately an optional observer.  It never raises into the
request path and it records identifiers and pipeline decisions, not answer or
evidence text.  Raw questions are opt-in because they may contain personal
financial context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class JsonlTraceSettings:
    path: str = ""
    include_question: bool = False

    @classmethod
    def from_env(cls) -> "JsonlTraceSettings":
        return cls(
            path=os.getenv("PENSION_TRACE_PATH", "").strip(),
            include_question=_enabled(os.getenv("PENSION_TRACE_INCLUDE_QUESTION")),
        )


class JsonlTraceWriter:
    """Append a compact, JSON-serialisable request trace to a local file."""

    schema_version = "pension-agent.trace.v1"

    def __init__(self, settings: JsonlTraceSettings):
        if not settings.path:
            raise ValueError("PENSION_TRACE_PATH is required for JSONL tracing")
        self.settings = settings
        self.path = Path(settings.path)

    @classmethod
    def from_env(cls) -> "JsonlTraceWriter | None":
        settings = JsonlTraceSettings.from_env()
        return cls(settings) if settings.path else None

    @staticmethod
    def _question_hash(question: str) -> str:
        return hashlib.sha256(question.encode("utf-8")).hexdigest()

    @staticmethod
    def _list(trace: dict[str, Any], key: str) -> list[Any]:
        value = trace.get(key, [])
        return list(value) if isinstance(value, (list, tuple)) else []

    def record(
        self,
        *,
        question: str,
        think_trace: dict[str, Any],
        request_id: str | None,
        endpoint: str,
        question_id: str | None = None,
    ) -> None:
        """Write one trace line.

        ``os.O_APPEND`` keeps an individual short JSONL write coherent when a
        multi-worker server appends to the same local file.
        """
        trace = think_trace if isinstance(think_trace, dict) else {}
        record: dict[str, Any] = {
            "schema_version": self.schema_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "question_id": question_id,
            "endpoint": endpoint,
            "question_sha256": self._question_hash(question),
            "route": trace.get("route"),
            "active_subject": trace.get("active_subject"),
            "frontend_status": trace.get("frontend_status"),
            "frontend_reason": trace.get("frontend_reason"),
            "selected_requirements": self._list(trace, "selected_requirements"),
            "retrieved_chunk_ids": self._list(trace, "retrieved_chunk_ids"),
            "selected_evidence_chunk_ids": self._list(trace, "selected_evidence_chunk_ids"),
            "cited_chunk_ids": self._list(trace, "cited_chunk_ids"),
            "evidence_status": trace.get("evidence_status"),
            "outcome": trace.get("outcome"),
            "assessment_reason": trace.get("assessment_reason"),
            "generation_model": trace.get("generation_model"),
            "generator_called": trace.get("generator_called"),
            "generation_latency_ms": trace.get("generation_latency_ms"),
            "generation_error": trace.get("generation_error"),
        }
        if self.settings.include_question:
            record["question"] = question
        payload = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, payload)
        finally:
            os.close(descriptor)
