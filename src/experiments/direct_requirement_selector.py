"""P39 isolated direct canonical-requirement selector.

This module deliberately does *not* import the candidate Agent, retriever,
matcher, citation validator, or financial policy.  HCX is asked only to select
from a closed multi-label requirement vocabulary.  Product identity remains a
deterministic extraction from the user's question.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
import urllib.error

from src.experiments.hcx_semantic_planner import lexically_normalize
from src.generation.errors import GenerationError
from src.generation.hcx import UrllibTransport
from src.generation.rate_limit import GlobalMinIntervalLimiter


# A requirement is an evidence-bearing factual unit, not a broad intent such
# as ``tax`` or ``withdrawal``.  The descriptions are supplied to HCX so the
# enum names do not depend on English identifier interpretation.
DIRECT_REQUIREMENT_LABELS: dict[str, str] = {
    "DB.operation_party": "DB형 적립금 운용 주체",
    "DC.operation_party": "DC형 적립금 운용 주체",
    "DB.benefit_determination": "DB형 퇴직급여 산식·계산 방식(퇴직 전 평균임금 30일분과 계속근로기간)",
    "DC.benefit_determination": "DC형 퇴직급여 결정 방식",
    "DC.employer_contribution": "DC형 사용자의 부담금 적립 기준",
    "retirement_pension.participant_education.frequency": "퇴직연금 가입자 교육 최소 실시 주기",
    "retirement_pension.participant_education.outsourcing": "퇴직연금 가입자 교육 외부 위탁 가능 여부",
    "pension_savings.tax_credit.limit": "연금저축 단독 세액공제 대상 한도",
    "pension_savings_IRP.tax_credit.combined_limit": "연금저축과 IRP 합산 세액공제 대상 한도",
    "general_account.investment_income.tax_timing": "일반 투자계좌 운용이익 과세 시점",
    "pension_account.investment_income.tax_timing": "연금계좌 운용이익 과세 시점 또는 과세이연",
    "pension_account.investment_income.not_tax_exempt": "연금계좌 과세이연이 면세가 아니라는 설명",
    "foreign_ETF.general_account.tax_timing": "국내 거래소 해외 ETF의 일반계좌 과세 시점",
    "foreign_ETF.pension_account.tax_timing": "국내 거래소 해외 ETF의 연금계좌 과세 시점",
    "DC.early_withdrawal.allowed_reasons": "DC형 퇴직연금의 퇴직 전 중도인출 법정사유",
    "DC.early_withdrawal.required_documents": "DC형 퇴직연금 중도인출 때 법정사유에 따라 필요한 증빙서류",
    "pension_savings.early_withdrawal.allowed_reasons": "연금저축의 연금수령 전 인출 가능 조건",
    "IRP.early_withdrawal.allowed_reasons": "IRP의 연금수령 전 중도인출 법정사유",
    "pension_savings.withdrawal.tax_treatment": "연금저축 인출 과세 처리",
    "IRP.withdrawal.tax_treatment": "IRP 인출 과세 처리",
    "ISA.transfer.deadline": "ISA 만기자금의 연금계좌 이전 기한",
    "ISA.transfer.additional_tax_credit": "ISA 만기자금 이전 추가 세액공제 산식과 한도",
    "retirement_pension.in_kind_transfer.definition": "퇴직연금 실물이전의 의미",
    "retirement_pension.in_kind_transfer.DB_DC.application_route": "DB·DC 재직자의 실물이전 신청 경로",
    "retirement_pension.in_kind_transfer.IRP.application_route": "IRP 가입자의 실물이전 신청 경로",
    "retirement_pension.ETF.direct_trade_scope": "퇴직연금 계좌에서 ETF 직접매매 가능 범위",
    "retirement_pension.ETF.leverage_inverse_restriction": "퇴직연금 계좌의 레버리지·인버스 ETF 제한",
    "product.risk_grade.current": "질문에서 식별된 상품의 현재 위험등급",
    "product.risk_grade.change_possibility": "질문에서 식별된 상품 위험등급의 향후 변경 가능성",
    "product.risk_grade.historical": "질문에서 식별된 상품의 과거 위험등급 또는 변경 이력",
    "product.tracking_index": "질문에서 식별된 상품의 추종 기준지수",
    "product.equity_allocation_limit": "질문에서 식별된 상품의 주식성 자산 최대 편입 비중",
    "product.total_fee": "질문에서 식별된 상품의 연간 총보수율",
    "product.period_cost": "질문에서 식별된 상품의 기간별 비용 예시 금액",
    "retirement_income.IRP_transfer.tax_timing": "퇴직급여를 IRP로 이전한 뒤 과세되는 시점",
    "pension_account.partial_withdrawal.condition": "연금계좌 일부 인출의 조건 또는 성격",
    "pension_account.partial_withdrawal.tax_treatment": "연금계좌 일부 인출의 과세 처리",
    "pension_account.account_closure.condition": "연금계좌 해지·전액 수령의 조건 또는 성격",
    "pension_account.account_closure.tax_treatment": "연금계좌 해지·전액 수령의 과세 처리",
}
DIRECT_REQUIREMENTS = tuple(DIRECT_REQUIREMENT_LABELS)
_PRODUCT_CODE = re.compile(r"KR[A-Z0-9]{10}", re.IGNORECASE)

# These scope rules are used only by the isolated P41-B selector experiment.
# The established P39 selector continues to receive the full enum unless a
# caller explicitly supplies a uniquely resolved active subject.
_SCOPE_PREFIXES: dict[str, tuple[str, ...]] = {
    "DB": ("DB.", "retirement_pension.participant_education.", "retirement_pension.in_kind_transfer.DB_DC."),
    "DC": ("DC.", "retirement_pension.participant_education.", "retirement_pension.in_kind_transfer.DB_DC.", "retirement_pension.ETF."),
    "IRP": ("IRP.", "retirement_income.IRP", "retirement_pension.in_kind_transfer.IRP."),
    "pension_savings": ("pension_savings.",),
    "ISA": ("ISA.",),
}


def resolve_product_codes(question: str) -> tuple[str, ...]:
    """Resolve explicit product codes without asking HCX to infer identity."""
    return tuple(dict.fromkeys(match.group(0).upper() for match in _PRODUCT_CODE.finditer(question)))


def requirements_for_active_subject(subject: str) -> tuple[str, ...]:
    """Return the closed selector catalog compatible with one resolved scope.

    This intentionally raises for plural/unknown scopes: filtering an enum
    when scope is not unique would turn uncertainty into an unsafe exclusion.
    """
    if subject.startswith("product:"):
        return tuple(key for key in DIRECT_REQUIREMENTS if key.startswith("product."))
    prefixes = _SCOPE_PREFIXES.get(subject)
    if not prefixes:
        raise ValueError(f"no subject-filtered requirement catalog for {subject!r}")
    return tuple(key for key in DIRECT_REQUIREMENTS if key.startswith(prefixes))


@dataclass(frozen=True)
class DirectRequirementSelection:
    selected_requirements: tuple[str, ...]
    resolved_product_codes: tuple[str, ...]
    unresolved: bool
    schema_valid: bool
    ontology_valid: bool
    unknown_requirements: tuple[str, ...]
    diagnostic: dict


class DirectRequirementSelectorPromptBuilder:
    """Native SO contract for a precision-first, multi-label classifier."""

    response_schema = {
        "type": "object",
        "properties": {
            "selected_requirements": {
                "type": "array",
                "items": {"type": "string", "enum": list(DIRECT_REQUIREMENTS)},
            },
            "unresolved": {"type": "boolean"},
        },
        "required": ["selected_requirements", "unresolved"],
    }

    def payload(
        self,
        question: str,
        model: str,
        *,
        allowed_requirements: tuple[str, ...] | None = None,
        active_subjects: tuple[str, ...] = (),
    ) -> dict:
        if model.upper() != "HCX-007":
            raise ValueError("P39 direct selector requires HCX-007 Native Structured Outputs")
        allowed = allowed_requirements or DIRECT_REQUIREMENTS
        unknown = tuple(value for value in allowed if value not in DIRECT_REQUIREMENT_LABELS)
        if unknown:
            raise ValueError(f"unknown allowed requirement: {unknown}")
        catalog = "\n".join(f"- {key}: {DIRECT_REQUIREMENT_LABELS[key]}" for key in allowed)
        scope_instruction = (
            "No active subject scope was supplied; use the complete catalog."
            if not active_subjects else
            f"The resolver has uniquely fixed the active subject scope to: {', '.join(active_subjects)}. "
            "Select only from the displayed scope-compatible catalog."
        )
        prompt = (
            "You are a requirement selector, not an answer writer. Return only the Structured Output object. "
            "Do not answer, retrieve, cite, invent facts, or make a requirement name.\n\n"
            "Choose every and only the evidence-bearing factual requirement explicitly or semantically requested "
            "by this Korean closed factual question. This is multi-label: independently requested facts require "
            "separate selections. Do not choose a merely related fact. Product codes are resolved deterministically "
            "outside this task, so select product.* fields only when the question requests that factual field. "
            "If no listed requirement can safely represent the question, set unresolved=true and select none. "
            "Precision rule: do not select a related, contextual, or same-subject fact unless the user explicitly or "
            "semantically requests that factual dimension. In particular, product.total_fee (annual total fee rate) and "
            "product.period_cost (example monetary cost for a holding period) are distinct: select both only if the "
            "question independently asks both factual dimensions. Questions about a DB retirement-benefit formula, "
            "benefit calculation, or average-wage-days calculation map to DB.benefit_determination.\n\n"
            f"[Scope]\n{scope_instruction}\n\n"
            "[Allowed requirement catalog]\n"
            f"{catalog}\n\n"
            f"[Question]\n{question}"
        )
        return {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "maxCompletionTokens": 400,
            "thinking": {"effort": "none"},
            "responseFormat": {
                "type": "json",
                "schema": {
                    **self.response_schema,
                    "properties": {
                        **self.response_schema["properties"],
                        "selected_requirements": {
                            **self.response_schema["properties"]["selected_requirements"],
                            "items": {"type": "string", "enum": list(allowed)},
                        },
                    },
                },
            },
        }


class DirectRequirementSelectionValidator:
    def validate(
        self,
        parsed: object,
        *,
        question: str,
        diagnostic: dict,
        allowed_requirements: tuple[str, ...] | None = None,
    ) -> DirectRequirementSelection:
        if not isinstance(parsed, dict):
            return self._invalid(question, diagnostic, "response_not_object")
        values, unresolved = parsed.get("selected_requirements"), parsed.get("unresolved")
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            return self._invalid(question, diagnostic, "selected_requirements_not_string_array")
        if not isinstance(unresolved, bool):
            return self._invalid(question, diagnostic, "unresolved_not_boolean")
        selected = tuple(sorted(set(values)))
        allowed = set(allowed_requirements or DIRECT_REQUIREMENTS)
        unknown = tuple(value for value in selected if value not in allowed)
        return DirectRequirementSelection(
            tuple(value for value in selected if value in allowed),
            resolve_product_codes(question), unresolved, True, not unknown, unknown,
            {**diagnostic, "unknown_requirements": list(unknown)},
        )

    @staticmethod
    def _invalid(question: str, diagnostic: dict, reason: str) -> DirectRequirementSelection:
        return DirectRequirementSelection((), resolve_product_codes(question), True, False, False, (), {
            **diagnostic, "validation_error": reason, "unknown_requirements": [],
        })


class HCXDirectRequirementSelector:
    """Isolated HCX wrapper.  It has no access to Agent execution paths."""

    def __init__(self, *, config, transport=None, rate_limiter=None, sleeper=time.sleep):
        self.config = config
        self.transport = transport or UrllibTransport()
        self.rate_limiter = rate_limiter or GlobalMinIntervalLimiter(
            config.hcx_min_interval_seconds, guard_seconds=config.hcx_pacing_guard_seconds,
        )
        self.sleeper = sleeper
        self.prompt_builder = DirectRequirementSelectorPromptBuilder()
        self.validator = DirectRequirementSelectionValidator()

    @staticmethod
    def _content(body: str) -> str:
        data = json.loads(body)
        result = data.get("result", {}) if isinstance(data, dict) else {}
        message = result.get("message", {}) if isinstance(result, dict) else {}
        content = message.get("content") or data.get("message", {}).get("content") or data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("HCX direct selector response has no message content")
        return content

    def select(
        self,
        question: str,
        *,
        allowed_requirements: tuple[str, ...] | None = None,
        active_subjects: tuple[str, ...] = (),
    ) -> DirectRequirementSelection:
        normalized = lexically_normalize(question)
        payload = self.prompt_builder.payload(
            normalized,
            self.config.hcx_model,
            allowed_requirements=allowed_requirements,
            active_subjects=active_subjects,
        )
        headers = {"Authorization": f"Bearer {self.config.hcx_api_key}", "Content-Type": "application/json"}
        started, attempts = time.perf_counter(), []
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
                    raise GenerationError("HCX direct selector unavailable", diagnostic={**diagnostic, "attempts": attempts})
                if status >= 400:
                    raise GenerationError("HCX direct selector request failed", diagnostic={**diagnostic, "attempts": attempts})
                parsed = json.loads(self._content(body))
                attempts.append({**diagnostic, "outcome": "success"})
                return self.validator.validate(
                    parsed,
                    question=question,
                    diagnostic={**diagnostic, "attempts": attempts},
                    allowed_requirements=allowed_requirements,
                )
            except GenerationError:
                raise
            except Exception as exc:
                attempts.append({**diagnostic, "exception_type": type(exc).__name__, "outcome": "failed"})
                if attempt < self.config.max_retries:
                    self.sleeper(0.1 * (attempt + 1))
                    continue
                raise GenerationError("HCX direct selector response invalid", diagnostic={**diagnostic, "attempts": attempts}) from exc
