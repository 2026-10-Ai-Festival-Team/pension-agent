"""Attribute frozen P38-2 atom failures without changing or running the parser."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "evaluation/p38_2_semantic_atom_holdout_results.json"
OUTPUT = ROOT / "evaluation/p38_2_semantic_atom_failure_attribution.json"

# Vocabulary observed in the frozen P38-1 development specification. A gold
# atom absent here is a representation/ontology issue, not merely a parser miss.
DEVELOPMENT_ONTOLOGY = {
    "subjects": {"account:DB", "account:DC", "account:IRP", "account:ISA", "account:general", "account:pension", "account:pension_savings", "system:retirement_pension", "product:foreign_etf", "product:KR510902773M", "product:KR5114420022", "product:KR5114450222", "product:KR5120420039", "product:KR5120420091", "product:KR5127450215"},
    "actions": {"contribute", "withdraw", "transfer", "receive", "manage", "invest", "compare", "educate"},
    "fields": {"operation_party", "benefit_determination", "contribution_structure", "education_provider", "education_frequency", "education_outsourcing", "etf_direct_trade", "leverage_inverse_restriction", "tax_credit_limit", "tax_timing", "withdrawal_reason", "required_document", "procedure", "tax_treatment", "transfer_deadline", "transfer_definition", "application_route", "risk_grade", "risk_grade_changeability", "tracking_index", "equity_allocation_limit", "total_fee", "cost_example"},
    "modifiers": {"account_specific", "comparison", "combined_limit", "before_retirement", "current", "change_possibility", "maturity_event", "additional_credit", "in_kind", "annual_rate", "holding_period", "field_boundary", "relative_low_risk", "not_tax_exempt"},
}

FAMILY_BY_ID = {
    "P38-2-002": "withdrawal_document", "P38-2-007": "withdrawal_document", "P38-2-018": "withdrawal_document",
    "P38-2-004": "contribution_comparison", "P38-2-005": "contribution_comparison", "P38-2-006": "contribution_comparison",
    "P38-2-008": "transfer", "P38-2-009": "transfer", "P38-2-017": "transfer",
    "P38-2-012": "product_field_time", "P38-2-013": "product_field_time", "P38-2-015": "product_field_time",
}


def _diff(detail: dict) -> dict[str, dict[str, list[str]]]:
    return {
        component: {
            "missing": sorted(set(detail["gold"][component]) - set(detail["predicted"][component])),
            "unexpected": sorted(set(detail["predicted"][component]) - set(detail["gold"][component])),
        }
        for component in ("subjects", "actions", "fields", "modifiers")
    }


def _owner(diff: dict[str, dict[str, list[str]]], requirement_exact: bool) -> str | None:
    if requirement_exact:
        return None
    for component in ("subjects", "actions", "fields", "modifiers"):
        if any(atom not in DEVELOPMENT_ONTOLOGY[component] for atom in diff[component]["missing"]):
            return "ontology_gap"
    if diff["subjects"]["missing"]:
        return "subject_miss"
    missing_components = [component for component in ("actions", "fields", "modifiers") if diff[component]["missing"]]
    if len(missing_components) >= 2 or sum(len(diff[component]["missing"]) for component in missing_components) >= 2:
        return "multi_atom_miss"
    if diff["actions"]["missing"] or diff["actions"]["unexpected"]:
        return "action_miss"
    if diff["fields"]["missing"] or diff["fields"]["unexpected"]:
        return "field_miss"
    if diff["modifiers"]["missing"] or diff["modifiers"]["unexpected"]:
        return "modifier_miss"
    return "composition_miss"


def attribute() -> dict:
    result = json.loads(INPUT.read_text(encoding="utf-8"))
    failures = []
    for detail in result["details"]:
        if detail["requirement_exact"]:
            continue
        diff = _diff(detail)
        failures.append({
            "source_question_id": detail["source_question_id"],
            "primary_owner": _owner(diff, detail["requirement_exact"]),
            "failure_family": FAMILY_BY_ID.get(detail["source_question_id"], "other_closed_factual"),
            "atom_diff": diff,
            "predicted_requirements": detail["predicted_requirements"],
            "gold_requirements": detail["gold_requirements"],
            "requirement_exact": False,
        })
    owners = ("subject_miss", "action_miss", "field_miss", "modifier_miss", "multi_atom_miss", "composition_miss", "ontology_gap", "semantic_binding_error")
    families = ("withdrawal_document", "contribution_comparison", "transfer", "product_field_time", "other_closed_factual")
    return {
        "experiment": "P38-2A frozen atom-level failure attribution",
        "input_execution": str(INPUT.relative_to(ROOT)),
        "hcx_calls": 0,
        "candidate_agent_changed": False,
        "parser_changed": False,
        "failure_count": len(failures),
        "primary_owner_summary": {owner: sum(item["primary_owner"] == owner for item in failures) for owner in owners},
        "failure_family_summary": {family: sum(item["failure_family"] == family for item in failures) for family in families},
        "failures": failures,
    }


def main() -> None:
    report = attribute()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"failure_count": report["failure_count"], "owners": report["primary_owner_summary"], "families": report["failure_family_summary"], "hcx_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
