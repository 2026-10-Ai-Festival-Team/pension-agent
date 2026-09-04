"""P38-3 isolated HCX structured semantic planner.

This experiment intentionally has no retrieval context, answer generation,
citation, or candidate-Agent import.  HCX may choose only ontology values; a
local validator remains the final authority for the returned plan.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
import urllib.error

from src.experiments.compositional_canonicalizer import SemanticAtoms
from src.generation.errors import GenerationError
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


ONTOLOGY = {
    "subjects": (
        "account:DB", "account:DC", "account:IRP", "account:ISA", "account:general",
        "account:pension", "account:pension_savings", "system:retirement_pension",
        "product:foreign_etf", "product:KR510902773M", "product:KR5114420022",
        "product:KR5114450222", "product:KR5120420039", "product:KR5120420091",
        "product:KR5127450215",
    ),
    "actions": ("contribute", "withdraw", "transfer", "receive", "manage", "invest", "compare", "educate"),
    "fields": (
        "operation_party", "benefit_determination", "contribution_structure", "education_provider",
        "education_frequency", "education_outsourcing", "etf_direct_trade",
        "leverage_inverse_restriction", "tax_credit_limit", "tax_timing", "withdrawal_reason",
        "required_document", "procedure", "tax_treatment", "transfer_deadline",
        "transfer_definition", "application_route", "risk_grade", "risk_grade_changeability",
        "tracking_index", "equity_allocation_limit", "total_fee", "cost_example",
    ),
    # ``historical`` remains intentionally excluded: P38-2A identified it as
    # a current ontology gap. The experiment must record that gap rather than
    # silently extend the representation while testing HCX extraction.
    "modifiers": (
        "account_specific", "comparison", "combined_limit", "before_retirement", "current",
        "change_possibility", "maturity_event", "additional_credit", "in_kind", "annual_rate",
        "holding_period", "field_boundary", "relative_low_risk", "not_tax_exempt",
    ),
}


_LEXICAL_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    # These are identity-only rewrites.  They deliberately do not infer an
    # operation or factual field (that remains HCX's isolated responsibility).
    (re.compile(r"연\s*저"), "연금저축"),
    (re.compile(r"개인형\s*퇴직\s*연금"), "IRP"),
    (re.compile(r"확정급여형"), "DB"),
    (re.compile(r"확정기여형"), "DC"),
)
_PRODUCT_CODE = re.compile(r"KR[A-Z0-9]{10}", re.IGNORECASE)


def lexically_normalize(question: str) -> str:
    """Normalize only explicit aliases, spacing, and product-code casing.

    P38-3 must not reintroduce semantic phrase routing before HCX.  This
    function is intentionally restricted to unambiguous entity aliases and
    presentation cleanup.
    """
    normalized = " ".join(question.strip().split())
    for pattern, replacement in _LEXICAL_REWRITES:
        normalized = pattern.sub(replacement, normalized)
    return _PRODUCT_CODE.sub(lambda match: match.group(0).upper(), normalized)


@dataclass(frozen=True)
class SemanticPlanResponse:
    atoms: SemanticAtoms
    schema_valid: bool
    ontology_valid: bool
    unknown_atoms: tuple[str, ...]
    diagnostic: dict


class SemanticPlannerPromptBuilder:
    """Build an HCX-007 native Structured Output payload for semantic atoms."""

    response_schema = {
        "type": "object",
        "properties": {
            name: {
                "type": "array",
                "items": {"type": "string", "enum": list(values)},
            }
            for name, values in ONTOLOGY.items()
        },
        "required": ["subjects", "actions", "fields", "modifiers"],
    }

    def payload(self, question: str, model: str) -> dict:
        if model.upper() != "HCX-007":
            raise ValueError("P38-3 Native Structured Outputs requires HCX-007")
        prompt = (
            "You are a semantic parser, not an answer writer. Extract every factual requirement from the Korean question. "
            "Return only the Structured Output object. Do not explain, answer the question, cite documents, invent facts, "
            "or use values outside the supplied enum. Arrays may be empty only when the question does not express that atom type.\n\n"
            "Interpret the atom types as follows: subjects are account/system/product identities; actions are requested operations; "
            "fields are factual attributes; modifiers are conditions such as comparison, before retirement, or current. "
            "Preserve multiple independently requested fields.\n\n"
            f"[Question]\n{question}"
        )
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 400,
            "thinking": {"effort": "none"},
            "responseFormat": {"type": "json", "schema": self.response_schema},
        }


class SemanticPlanValidator:
    """Fail closed on malformed/unknown atoms after API-level enum constraints."""

    def validate(self, parsed: object, diagnostic: dict) -> SemanticPlanResponse:
        if not isinstance(parsed, dict):
            return self._invalid(diagnostic, "response_not_object")
        unknown = []
        values: dict[str, tuple[str, ...]] = {}
        for component, allowed in ONTOLOGY.items():
            raw = parsed.get(component)
            if not isinstance(raw, list) or not all(isinstance(value, str) for value in raw):
                return self._invalid(diagnostic, f"{component}_not_string_array")
            deduplicated = tuple(sorted(set(raw)))
            unknown.extend(f"{component}:{value}" for value in deduplicated if value not in allowed)
            values[component] = tuple(value for value in deduplicated if value in allowed)
        diagnostic = {**diagnostic, "unknown_atoms": sorted(unknown)}
        if unknown:
            return SemanticPlanResponse(
                SemanticAtoms(values["subjects"], values["actions"], values["fields"], values["modifiers"]),
                schema_valid=True,
                ontology_valid=False,
                unknown_atoms=tuple(sorted(unknown)),
                diagnostic=diagnostic,
            )
        return SemanticPlanResponse(
            SemanticAtoms(values["subjects"], values["actions"], values["fields"], values["modifiers"]),
            schema_valid=True,
            ontology_valid=True,
            unknown_atoms=(),
            diagnostic=diagnostic,
        )

    @staticmethod
    def _invalid(diagnostic: dict, reason: str) -> SemanticPlanResponse:
        return SemanticPlanResponse(
            SemanticAtoms((), (), (), ()),
            schema_valid=False,
            ontology_valid=False,
            unknown_atoms=(),
            diagnostic={**diagnostic, "validation_error": reason, "unknown_atoms": []},
        )


class HCXSemanticPlanner:
    """HCX transport wrapper dedicated to P38-3 semantic plans."""

    def __init__(self, *, config, transport=None, rate_limiter=None, sleeper=time.sleep, response_capture=None):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(
            config.hcx_min_interval_seconds,
            guard_seconds=config.hcx_pacing_guard_seconds,
        )
        self.sleeper = sleeper
        self.response_capture = response_capture
        self.prompt_builder = SemanticPlannerPromptBuilder()
        self.validator = SemanticPlanValidator()

    @staticmethod
    def _content(body: str) -> str:
        data = json.loads(body)
        result = data.get("result", {}) if isinstance(data, dict) else {}
        message = result.get("message", {}) if isinstance(result, dict) else {}
        content = message.get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("HCX semantic response has no message content")
        return content

    def plan(self, question: str) -> SemanticPlanResponse:
        normalized_question = lexically_normalize(question)
        payload = self.prompt_builder.payload(normalized_question, self.config.hcx_model)
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        started = time.perf_counter()
        attempts = []
        for attempt in range(self.config.max_retries + 1):
            diagnostic = {
                "attempt": attempt + 1,
                "request_payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                "lexical_normalization_applied": normalized_question != question,
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
                if self.response_capture is not None:
                    self.response_capture(status, body)
                if status == 429 or status >= 500:
                    attempts.append({**diagnostic, "outcome": "retry" if attempt < self.config.max_retries else "failed"})
                    if attempt < self.config.max_retries:
                        self.sleeper(0.1 * (attempt + 1))
                        continue
                    raise GenerationError("HCX semantic planner unavailable", diagnostic={**diagnostic, "attempts": attempts})
                if status >= 400:
                    raise GenerationError("HCX semantic planner request failed", diagnostic={**diagnostic, "attempts": attempts})
                content = self._content(body)
                parsed = json.loads(content)
                attempts.append({**diagnostic, "outcome": "success"})
                return self.validator.validate(parsed, {**diagnostic, "attempts": attempts})
            except GenerationError:
                raise
            except Exception as exc:
                attempts.append({**diagnostic, "exception_type": type(exc).__name__, "outcome": "failed"})
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX semantic planner response invalid", diagnostic={**diagnostic, "attempts": attempts}) from exc
