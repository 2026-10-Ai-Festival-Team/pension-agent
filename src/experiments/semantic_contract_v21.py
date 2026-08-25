"""P38-7B v2.1 semantic contract, isolated from the candidate Agent.

The model emits only evidence-changing subjects, fields, qualifiers, and
directional transfers.  Generic comparisons are derived deterministically from
the raw question after the HCX output has been validated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from src.experiments.semantic_contract_v2 import ESSENTIAL_QUALIFIERS, FIELDS, SUBJECTS


TRANSFER = "transfer"
_COMPARISON_CUES = re.compile(
    r"비교|차이|다르|다른|각각|서로|나란히|구별|어느\s*(?:쪽|것)|때와.*때|경우와.*경우|중.*(?:무엇|어느)",
    re.DOTALL,
)
_PARTIAL_CLOSURE_COMPARISON_FIELDS = {
    "partial_withdrawal_condition", "account_closure_condition",
}


@dataclass(frozen=True)
class DirectionalTransfer:
    source: str
    destination: str


@dataclass(frozen=True)
class SemanticPlanV21:
    subjects: tuple[str, ...]
    fields: tuple[str, ...]
    qualifiers: tuple[str, ...]
    transfers: tuple[DirectionalTransfer, ...] = ()


class SemanticContractV21Validator:
    """Strict validation; account and system scopes are deliberately distinct."""

    @staticmethod
    def validate(plan: SemanticPlanV21) -> tuple[str, ...]:
        errors = []
        errors.extend(f"subject:{value}" for value in plan.subjects if value not in SUBJECTS)
        errors.extend(f"field:{value}" for value in plan.fields if value not in FIELDS)
        errors.extend(f"qualifier:{value}" for value in plan.qualifiers if value not in ESSENTIAL_QUALIFIERS)
        for transfer in plan.transfers:
            if transfer.source not in SUBJECTS:
                errors.append(f"transfer_source:{transfer.source}")
            if transfer.destination not in SUBJECTS:
                errors.append(f"transfer_destination:{transfer.destination}")
            if transfer.source == transfer.destination:
                errors.append("transfer_same_endpoint")
        return tuple(sorted(errors))


def has_comparison_intent(question: str, plan: SemanticPlanV21) -> bool:
    """Derive generic comparison only from question intent plus comparison scope.

    Two account/product subjects are sufficient scope.  A single account also
    supports comparison when the factual fields explicitly distinguish partial
    withdrawal from account closure.
    """
    scope_present = len(set(plan.subjects)) >= 2 or _PARTIAL_CLOSURE_COMPARISON_FIELDS <= set(plan.fields)
    return scope_present and bool(_COMPARISON_CUES.search(question))


class RequirementComposerV21:
    """Compose factual requirements without asking HCX to duplicate comparison."""

    _EARLY_WITHDRAWAL_FIELDS = {
        "withdrawal_reason": "allowed_reason",
        "required_document": "required_document",
        "procedure": "procedure",
    }
    _PARTIAL_CLOSURE_FIELDS = {
        "partial_withdrawal_condition": "partial_withdrawal.condition",
        "account_closure_condition": "account_closure.condition",
        "partial_withdrawal_tax": "partial_withdrawal.tax_treatment",
        "account_closure_tax": "account_closure.tax_treatment",
    }

    @classmethod
    def compose(cls, question: str, plan: SemanticPlanV21) -> tuple[str, ...]:
        errors = SemanticContractV21Validator.validate(plan)
        if errors:
            raise ValueError(f"Invalid semantic contract v2.1 plan: {', '.join(errors)}")
        subjects = "+".join(sorted(plan.subjects))
        qualifiers = set(plan.qualifiers)
        requirements: set[str] = set()
        for field in plan.fields:
            if field in cls._EARLY_WITHDRAWAL_FIELDS:
                operation = "early_withdrawal" if "before_retirement" in qualifiers else "withdrawal"
                requirements.add(f"{subjects}.{operation}.{cls._EARLY_WITHDRAWAL_FIELDS[field]}")
            elif field in cls._PARTIAL_CLOSURE_FIELDS:
                requirements.add(f"{subjects}.{cls._PARTIAL_CLOSURE_FIELDS[field]}")
            elif field == "risk_grade" and {"current", "historical"} & qualifiers:
                for timing in sorted({"current", "historical"} & qualifiers):
                    requirements.add(f"{subjects}.risk_grade.{timing}")
            elif field == "tax_timing" and "tax_timing_on_transfer" in qualifiers:
                requirements.add(f"{subjects}.transfer.tax_timing")
            else:
                requirements.add(f"{subjects}.{field}")
        for transfer in plan.transfers:
            requirements.add(f"relation.transfer.{transfer.source}->{transfer.destination}")
        if has_comparison_intent(question, plan):
            requirements.add(f"relation.comparison.{subjects}<->{subjects}")
        return tuple(sorted(requirements))
