"""Isolated P38-6 HCX-007 parser for the minimal semantic contract v2."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
import urllib.error

from src.experiments.hcx_semantic_planner import lexically_normalize
from src.experiments.semantic_contract_v2 import (
    ESSENTIAL_QUALIFIERS,
    FIELDS,
    RELATION_TYPES,
    SUBJECTS,
    SemanticContractV2Validator,
    SemanticPlanV2,
    SemanticRelation,
)
from src.generation.errors import GenerationError
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


@dataclass(frozen=True)
class SemanticPlanV2Response:
    plan: SemanticPlanV2
    schema_valid: bool
    ontology_valid: bool
    unknown_atoms: tuple[str, ...]
    diagnostic: dict


class SemanticPlannerV2PromptBuilder:
    """Native SO payload; emits only v2 semantic atoms, never an answer."""

    _relation_subjects = ["", *SUBJECTS]
    _relation_sides = ["", "partial_withdrawal", "account_closure", *SUBJECTS]
    response_schema = {
        "type": "object",
        "properties": {
            "subjects": {"type": "array", "items": {"type": "string", "enum": list(SUBJECTS)}},
            "fields": {"type": "array", "items": {"type": "string", "enum": list(FIELDS)}},
            "essential_qualifiers": {"type": "array", "items": {"type": "string", "enum": list(ESSENTIAL_QUALIFIERS)}},
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": list(RELATION_TYPES)},
                        "source": {"type": "string", "enum": _relation_subjects},
                        "destination": {"type": "string", "enum": _relation_subjects},
                        "left": {"type": "string", "enum": _relation_sides},
                        "right": {"type": "string", "enum": _relation_sides},
                    },
                    "required": ["type", "source", "destination", "left", "right"],
                },
            },
        },
        "required": ["subjects", "fields", "essential_qualifiers", "relations"],
    }

    def payload(self, question: str, model: str) -> dict:
        if model.upper() != "HCX-007":
            raise ValueError("P38-6 Native Structured Outputs requires HCX-007")
        prompt = (
            "You are a semantic parser, not an answer writer. Return only the Structured Output object. "
            "Do not answer, retrieve, cite, invent facts, or output values outside the enum.\n\n"
            "Extract every factual retrieval requirement from the Korean question.\n"
            "- subjects: account, system, product, or retirement-benefit identities.\n"
            "- fields: the factual values being requested.\n"
            "- essential_qualifiers: include only a condition that changes the factual evidence needed. "
            "Examples: before_retirement, combined_limit, isa_maturity, in_kind, current, historical. "
            "Do not add a qualifier merely because it restates a field.\n"
            "- relations: use comparison for a factual comparison; use transfer only when source and destination matter. "
            "For unused relation properties emit an empty string.\n"
            "Preserve all independently requested fields and essential qualifiers.\n\n"
            f"[Question]\n{question}"
        )
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 450,
            "thinking": {"effort": "none"},
            "responseFormat": {"type": "json", "schema": self.response_schema},
        }


class SemanticPlanV2ResponseValidator:
    def validate(self, parsed: object, diagnostic: dict) -> SemanticPlanV2Response:
        if not isinstance(parsed, dict):
            return self._invalid(diagnostic, "response_not_object")
        required = ("subjects", "fields", "essential_qualifiers", "relations")
        if any(not isinstance(parsed.get(name), list) for name in required):
            return self._invalid(diagnostic, "component_not_array")
        if not all(isinstance(value, str) for name in required[:3] for value in parsed[name]):
            return self._invalid(diagnostic, "atom_not_string")
        relations = []
        for raw in parsed["relations"]:
            if not isinstance(raw, dict) or any(not isinstance(raw.get(name), str) for name in ("type", "source", "destination", "left", "right")):
                return self._invalid(diagnostic, "relation_not_complete_string_object")
            relations.append(SemanticRelation(
                raw["type"], raw["source"] or None, raw["destination"] or None,
                raw["left"] or None, raw["right"] or None,
            ))
        plan = SemanticPlanV2(
            tuple(sorted(set(parsed["subjects"]))),
            tuple(sorted(set(parsed["fields"]))),
            tuple(sorted(set(parsed["essential_qualifiers"]))),
            tuple(sorted(set(relations), key=lambda item: (item.type, item.source or "", item.destination or "", item.left or "", item.right or ""))),
        )
        unknown = SemanticContractV2Validator.validate(plan)
        diagnostic = {**diagnostic, "unknown_atoms": list(unknown)}
        return SemanticPlanV2Response(plan, True, not unknown, unknown, diagnostic)

    @staticmethod
    def _invalid(diagnostic: dict, reason: str) -> SemanticPlanV2Response:
        return SemanticPlanV2Response(SemanticPlanV2((), (), (), ()), False, False, (), {**diagnostic, "validation_error": reason, "unknown_atoms": []})


class HCXSemanticPlannerV2:
    """Dedicated P38-6 transport wrapper, deliberately outside candidate code."""

    def __init__(self, *, config, transport=None, rate_limiter=None, sleeper=time.sleep):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(config.hcx_min_interval_seconds, guard_seconds=config.hcx_pacing_guard_seconds)
        self.sleeper = sleeper
        self.prompt_builder = SemanticPlannerV2PromptBuilder()
        self.validator = SemanticPlanV2ResponseValidator()

    @staticmethod
    def _content(body: str) -> str:
        data = json.loads(body)
        result = data.get("result", {}) if isinstance(data, dict) else {}
        message = result.get("message", {}) if isinstance(result, dict) else {}
        content = message.get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("HCX semantic v2 response has no message content")
        return content

    def plan(self, question: str) -> SemanticPlanV2Response:
        normalized = lexically_normalize(question)
        payload = self.prompt_builder.payload(normalized, self.config.hcx_model)
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        attempts = []
        for attempt in range(self.config.max_retries + 1):
            diagnostic = {
                "attempt": attempt + 1,
                "request_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                "lexical_normalization_applied": normalized != question,
            }
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
                    raise GenerationError("HCX semantic v2 planner unavailable", diagnostic={**diagnostic, "attempts": attempts})
                if status >= 400:
                    raise GenerationError("HCX semantic v2 planner request failed", diagnostic={**diagnostic, "attempts": attempts})
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
                raise GenerationError("HCX semantic v2 planner response invalid", diagnostic={**diagnostic, "attempts": attempts}) from exc
