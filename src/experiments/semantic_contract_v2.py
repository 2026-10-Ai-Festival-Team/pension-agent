"""P38-5 minimal semantic contract v2, isolated from the candidate Agent.

V2 encodes only distinctions that change the factual evidence requirement:
subject, field, essential qualifier, and an explicit relationship.  Operations
such as ``withdraw`` are deterministically implied by field definitions rather
than required as an independent LLM-emitted atom.
"""
from __future__ import annotations

from dataclasses import dataclass


SUBJECTS = (
    "account:DB", "account:DC", "account:IRP", "account:ISA", "account:general",
    "account:pension", "account:pension_savings", "system:retirement_pension",
    "product:foreign_etf", "product:KR510902773M", "product:KR5114420022",
    "product:KR5114450222", "product:KR5120420039", "product:KR5120420091",
    "product:KR5127450215", "event:retirement_benefit",
)

FIELDS = (
    "operation_party", "benefit_determination", "contribution_structure",
    "education_provider", "education_frequency", "education_outsourcing",
    "etf_direct_trade", "leverage_inverse_restriction", "tax_credit_limit",
    "tax_timing", "withdrawal_reason", "required_document", "procedure",
    "tax_treatment", "transfer_deadline", "transfer_definition", "application_route",
    "risk_grade", "risk_grade_changeability", "tracking_index", "equity_allocation_limit",
    "total_fee", "cost_example", "partial_withdrawal_condition",
    "account_closure_condition", "partial_withdrawal_tax", "account_closure_tax",
)

# These qualifiers survive only where losing them changes the evidence scope.
ESSENTIAL_QUALIFIERS = (
    "before_retirement", "combined_limit", "isa_maturity", "additional_credit",
    "in_kind", "tax_timing_on_transfer", "not_tax_exempt", "current", "historical",
    "change_possibility",
)

RELATION_TYPES = ("comparison", "transfer")


@dataclass(frozen=True)
class SemanticRelation:
    type: str
    source: str | None = None
    destination: str | None = None
    left: str | None = None
    right: str | None = None


@dataclass(frozen=True)
class SemanticPlanV2:
    subjects: tuple[str, ...]
    fields: tuple[str, ...]
    qualifiers: tuple[str, ...]
    relations: tuple[SemanticRelation, ...] = ()


class SemanticContractV2Validator:
    """Strictly reject ontology values outside the minimal v2 contract."""

    @staticmethod
    def validate(plan: SemanticPlanV2) -> tuple[str, ...]:
        errors = []
        errors.extend(f"subject:{value}" for value in plan.subjects if value not in SUBJECTS)
        errors.extend(f"field:{value}" for value in plan.fields if value not in FIELDS)
        errors.extend(f"qualifier:{value}" for value in plan.qualifiers if value not in ESSENTIAL_QUALIFIERS)
        for relation in plan.relations:
            if relation.type not in RELATION_TYPES:
                errors.append(f"relation:{relation.type}")
            for value in (relation.source, relation.destination):
                if value is not None and value not in SUBJECTS:
                    errors.append(f"relation_subject:{value}")
        return tuple(sorted(errors))


class RequirementComposerV2:
    """Compose retrieval requirements from factual fields and essential scope."""

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
    def compose(cls, plan: SemanticPlanV2) -> tuple[str, ...]:
        errors = SemanticContractV2Validator.validate(plan)
        if errors:
            raise ValueError(f"Invalid semantic contract v2 plan: {', '.join(errors)}")
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
        for relation in plan.relations:
            if relation.type == "transfer":
                requirements.add(f"relation.transfer.{relation.source}->{relation.destination}")
            elif relation.type == "comparison":
                requirements.add(f"relation.comparison.{relation.left or subjects}<->{relation.right or subjects}")
        return tuple(sorted(requirements))
