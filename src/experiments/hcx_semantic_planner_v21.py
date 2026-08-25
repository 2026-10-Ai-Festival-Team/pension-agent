"""Isolated HCX-007 structured semantic parser for P38-7B contract v2.1."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
import urllib.error

from src.experiments.hcx_semantic_planner import lexically_normalize
from src.experiments.semantic_contract_v2 import ESSENTIAL_QUALIFIERS, FIELDS, SUBJECTS
from src.experiments.semantic_contract_v21 import (
    DirectionalTransfer,
    SemanticContractV21Validator,
    SemanticPlanV21,
)
from src.generation.errors import GenerationError
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


@dataclass(frozen=True)
class SemanticPlanV21Response:
    plan: SemanticPlanV21
    schema_valid: bool
    ontology_valid: bool
    unknown_atoms: tuple[str, ...]
    diagnostic: dict


class SemanticPlannerV21PromptBuilder:
    """Precision-first Native Structured Output request; never writes answers."""

    _relation_subjects = list(SUBJECTS)
    response_schema = {
        "type": "object",
        "properties": {
            "subjects": {"type": "array", "items": {"type": "string", "enum": list(SUBJECTS)}},
            "fields": {"type": "array", "items": {"type": "string", "enum": list(FIELDS)}},
            "essential_qualifiers": {"type": "array", "items": {"type": "string", "enum": list(ESSENTIAL_QUALIFIERS)}},
            "directional_transfers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "enum": _relation_subjects},
                        "destination": {"type": "string", "enum": _relation_subjects},
                    },
                    "required": ["source", "destination"],
                },
            },
        },
        "required": ["subjects", "fields", "essential_qualifiers", "directional_transfers"],
    }

    def payload(self, question: str, model: str) -> dict:
        if model.upper() != "HCX-007":
            raise ValueError("P38-7B Native Structured Outputs requires HCX-007")
        prompt = (
            "You are a semantic parser, not an answer writer. Return only the Structured Output object. "
            "Do not answer, retrieve, cite, invent facts, or output a value outside an enum.\n\n"
            "Extract only the factual distinctions explicitly or semantically requested by the Korean question. "
            "Precision is more important than completeness guesses: do NOT add a related account, system, product, "
            "event, field, qualifier, or future-change concept unless the question requires it. Use an empty array "
            "when a component is not requested.\n"
            "- subjects: exact account, system, product, or event scope. An account is not interchangeable with a broad system.\n"
            "- fields: exact factual values asked for. Keep distinct fields separate (for example partial withdrawal tax and account-closure tax).\n"
            "- essential_qualifiers: only a condition that changes required evidence, such as before_retirement, combined_limit, "
            "isa_maturity, additional_credit, in_kind, tax_timing_on_transfer, current, historical, or change_possibility.\n"
            "- directional_transfers: output only when source and destination change the factual scope. Preserve both endpoints.\n"
            "Do not output a generic comparison relation: comparison is inferred after parsing from the question and validated subjects.\n"
            "Preserve every independently requested field and essential qualifier, but add nothing else.\n\n"
            f"[Question]\n{question}"
        )
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 400,
            "thinking": {"effort": "none"},
            "responseFormat": {"type": "json", "schema": self.response_schema},
        }


class SemanticPlanV21ResponseValidator:
    def validate(self, parsed: object, diagnostic: dict) -> SemanticPlanV21Response:
        if not isinstance(parsed, dict):
            return self._invalid(diagnostic, "response_not_object")
        required = ("subjects", "fields", "essential_qualifiers", "directional_transfers")
        if any(not isinstance(parsed.get(name), list) for name in required):
            return self._invalid(diagnostic, "component_not_array")
        if not all(isinstance(value, str) for name in required[:3] for value in parsed[name]):
            return self._invalid(diagnostic, "atom_not_string")
        transfers = []
        for raw in parsed["directional_transfers"]:
            if not isinstance(raw, dict) or not all(isinstance(raw.get(name), str) for name in ("source", "destination")):
                return self._invalid(diagnostic, "transfer_not_complete_string_object")
            transfers.append(DirectionalTransfer(raw["source"], raw["destination"]))
        plan = SemanticPlanV21(
            tuple(sorted(set(parsed["subjects"]))), tuple(sorted(set(parsed["fields"]))),
            tuple(sorted(set(parsed["essential_qualifiers"]))),
            tuple(sorted(set(transfers), key=lambda item: (item.source, item.destination))),
        )
        unknown = SemanticContractV21Validator.validate(plan)
        return SemanticPlanV21Response(plan, True, not unknown, unknown, {**diagnostic, "unknown_atoms": list(unknown)})

    @staticmethod
    def _invalid(diagnostic: dict, reason: str) -> SemanticPlanV21Response:
        return SemanticPlanV21Response(SemanticPlanV21((), (), (), ()), False, False, (), {**diagnostic, "validation_error": reason, "unknown_atoms": []})


class HCXSemanticPlannerV21:
    """Dedicated transport wrapper, deliberately outside the candidate path."""

    def __init__(self, *, config, transport=None, rate_limiter=None, sleeper=time.sleep):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(config.hcx_min_interval_seconds, guard_seconds=config.hcx_pacing_guard_seconds)
        self.sleeper = sleeper
        self.prompt_builder = SemanticPlannerV21PromptBuilder()
        self.validator = SemanticPlanV21ResponseValidator()

    @staticmethod
    def _content(body: str) -> str:
        data = json.loads(body)
        result = data.get("result", {}) if isinstance(data, dict) else {}
        message = result.get("message", {}) if isinstance(result, dict) else {}
        content = message.get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("HCX semantic v2.1 response has no message content")
        return content

    def plan(self, question: str) -> SemanticPlanV21Response:
        normalized = lexically_normalize(question)
        payload = self.prompt_builder.payload(normalized, self.config.hcx_model)
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        started, attempts = time.perf_counter(), []
        for attempt in range(self.config.max_retries + 1):
            diagnostic = {"attempt": attempt + 1, "request_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")), "lexical_normalization_applied": normalized != question}
            try:
                diagnostic["rate_limit_wait_ms"] = round(self.rate_limiter.acquire() * 1000, 3)
                diagnostic["request_started_offset_ms"] = round((time.perf_counter() - started) * 1000, 3)
                try:
                    status, body = self.transport.post(self.config.hcx_base_url, headers, payload, self.config.timeout_seconds)
                except urllib.error.HTTPError as error:
                    status, body = error.code, error.read().decode(errors="replace")
                diagnostic["http_status"] = status
                diagnostic["request_completed_offset_ms"] = round((time.perf_counter() - started) * 1000, 3)
                diagnostic["raw_content_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
                if status == 429 or status >= 500:
                    attempts.append({**diagnostic, "outcome": "retry" if attempt < self.config.max_retries else "failed"})
                    if attempt < self.config.max_retries:
                        self.sleeper(0.1 * (attempt + 1))
                        continue
                    raise GenerationError("HCX semantic v2.1 planner unavailable", diagnostic={**diagnostic, "attempts": attempts})
                if status >= 400:
                    raise GenerationError("HCX semantic v2.1 planner request failed", diagnostic={**diagnostic, "attempts": attempts})
                parsed = json.loads(self._content(body))
                attempts.append({**diagnostic, "outcome": "success"})
                return self.validator.validate(parsed, {**diagnostic, "attempts": attempts})
            except GenerationError:
                raise
            except Exception as exc:
                attempts.append({**diagnostic, "exception_type": type(exc).__name__, "outcome": "failed"})
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX semantic v2.1 planner response invalid", diagnostic={**diagnostic, "attempts": attempts}) from exc
