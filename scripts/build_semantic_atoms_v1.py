"""Build a human-reviewed development specification for compositional parsing.

This is not an Agent input and is never consulted by routing, retrieval, or
generation.  It gives P38-0 a component-level gold set before redesigning the
canonicalizer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "question_bank/development/semantic_atoms_v1.jsonl"
METADATA = ROOT / "question_bank/development/semantic_atoms_v1_metadata.json"


# Development-only, manually reviewed semantic atom annotations.  The source
# questions have already lost fresh-holdout status (P36/P37); P38+ holdouts
# must never be copied into this file.
GOLD = {
    "P36-001": (["account:DB", "account:DC"], ["manage", "compare"], ["operation_party", "benefit_determination", "contribution_structure"], ["account_specific", "comparison"]),
    "P37-001": (["account:DB", "account:DC"], ["manage", "compare"], ["operation_party", "benefit_determination", "contribution_structure"], ["account_specific", "comparison"]),
    "P36-002": (["system:retirement_pension"], ["educate"], ["education_provider", "education_frequency", "education_outsourcing"], []),
    "P37-002": (["system:retirement_pension"], ["educate"], ["education_provider", "education_frequency", "education_outsourcing"], []),
    "P36-003": (["account:DC", "account:IRP"], ["invest"], ["etf_direct_trade", "leverage_inverse_restriction"], ["account_specific"]),
    "P37-011": (["system:retirement_pension"], ["invest"], ["etf_direct_trade", "leverage_inverse_restriction"], []),
    "P36-004": (["account:pension_savings", "account:IRP"], ["contribute", "compare"], ["tax_credit_limit"], ["account_specific", "combined_limit", "comparison"]),
    "P37-004": (["account:pension_savings", "account:IRP"], ["contribute", "compare"], ["tax_credit_limit"], ["account_specific", "combined_limit", "comparison"]),
    "P36-005": (["account:general", "account:pension"], ["receive", "compare"], ["tax_timing"], ["account_specific", "comparison", "not_tax_exempt"]),
    "P37-005": (["account:general", "account:pension"], ["receive", "compare"], ["tax_timing"], ["account_specific", "comparison", "not_tax_exempt"]),
    "P36-006": (["product:foreign_etf", "account:general", "account:pension"], ["invest", "compare"], ["tax_timing"], ["account_specific", "comparison"]),
    "P37-006": (["product:foreign_etf", "account:general", "account:pension"], ["invest", "compare"], ["tax_timing"], ["account_specific", "comparison"]),
    "P36-007": (["account:pension_savings", "account:IRP"], ["withdraw", "compare"], ["withdrawal_reason", "tax_treatment"], ["before_retirement", "account_specific", "comparison"]),
    "P37-007": (["account:pension_savings", "account:IRP"], ["withdraw", "compare"], ["withdrawal_reason", "tax_treatment"], ["before_retirement", "account_specific", "comparison"]),
    "P36-008": (["account:DC"], ["withdraw"], ["withdrawal_reason", "required_document", "procedure"], ["before_retirement"]),
    "P37-008": (["account:DC"], ["withdraw"], ["withdrawal_reason", "required_document", "procedure"], ["before_retirement"]),
    "P36-009": (["account:ISA", "account:pension"], ["transfer"], ["transfer_deadline", "tax_credit_limit"], ["account_specific", "maturity_event", "additional_credit"]),
    "P37-009": (["account:ISA", "account:pension"], ["transfer"], ["transfer_deadline", "tax_credit_limit"], ["account_specific", "maturity_event", "additional_credit"]),
    "P36-010": (["account:DB", "account:DC", "account:IRP"], ["transfer", "compare"], ["transfer_definition", "application_route"], ["in_kind", "account_specific", "comparison"]),
    "P37-010": (["account:DB", "account:DC", "account:IRP"], ["transfer", "compare"], ["transfer_definition", "application_route"], ["in_kind", "account_specific", "comparison"]),
    "P36-013": (["product:KR510902773M"], ["invest"], ["risk_grade", "risk_grade_changeability"], ["current", "change_possibility"]),
    "P37-013": (["product:KR510902773M"], ["invest"], ["risk_grade", "risk_grade_changeability"], ["current", "change_possibility"]),
    "P36-014": (["product:KR5127450215"], ["invest"], ["tracking_index", "equity_allocation_limit"], []),
    "P37-014": (["product:KR5127450215"], ["invest"], ["tracking_index", "equity_allocation_limit"], []),
    "P36-015": (["product:KR510902773M"], ["invest"], ["total_fee", "cost_example"], ["annual_rate", "holding_period", "field_boundary"]),
    "P37-015": (["product:KR510902773M"], ["invest"], ["total_fee", "cost_example"], ["annual_rate", "holding_period", "field_boundary"]),
    "P36-017": (["product:KR5114420022", "product:KR5114450222"], ["compare"], ["risk_grade"], ["comparison", "relative_low_risk"]),
    "P37-017": (["product:KR5114420022", "product:KR5114450222"], ["compare"], ["risk_grade"], ["comparison", "relative_low_risk"]),
    "P36-018": (["product:KR5120420039", "product:KR5120420091"], ["compare"], ["risk_grade"], ["comparison", "relative_low_risk"]),
    "P37-012": (["account:DB", "account:DC"], ["manage", "compare"], ["operation_party", "benefit_determination"], ["account_specific", "comparison"]),
}


def _source_questions() -> dict[str, str]:
    rows = {}
    for filename in ("p36_closed_holdout_manifest.json", "p37_closed_holdout_manifest.json"):
        manifest = json.loads((ROOT / "evaluation" / filename).read_text(encoding="utf-8"))
        rows.update({row["question_id"]: row["question"] for row in manifest["questions"]})
    return rows


def _requirements(subjects: list[str], actions: list[str], fields: list[str], modifiers: list[str]) -> list[str]:
    """Record intended composition without pretending each field has one subject."""
    subject_scope = "+".join(subjects)
    action_scope = "+".join(actions)
    modifier_scope = "+".join(modifiers) if modifiers else "none"
    return [f"{subject_scope}.{action_scope}.{field}[{modifier_scope}]" for field in fields]


def main() -> None:
    questions = _source_questions()
    if set(GOLD) - set(questions):
        raise SystemExit("semantic atom annotations reference missing source questions")
    rows = []
    for question_id, (subjects, actions, fields, modifiers) in GOLD.items():
        rows.append({
            "id": f"ATOM-{question_id}",
            "source_question_id": question_id,
            "split": "development_regression",
            "question": questions[question_id],
            "subjects": subjects,
            "actions": actions,
            "fields": fields,
            "modifiers": modifiers,
            "composed_requirements": _requirements(subjects, actions, fields, modifiers),
            "annotation_status": "human_reviewed_v1",
        })
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    metadata = {
        "version": "1.0",
        "purpose": "P38-0 compositional canonicalizer development specification",
        "question_count": len(rows),
        "source_sets": ["P36", "P37"],
        "status": "development_regression_only",
        "sha256": digest,
        "ontology": {
            "subjects": "account/system/product scoped identities",
            "actions": ["contribute", "withdraw", "transfer", "receive", "manage", "invest", "compare", "educate"],
            "fields": "closed factual attributes such as tax timing, withdrawal reason, risk grade, fee, or application route",
            "modifiers": "conditions such as before_retirement, current, change_possibility, combined_limit, or comparison",
        },
    }
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Tests redirect OUTPUT to a temporary directory, which is intentionally
    # outside ROOT.  Keep the builder usable in both repository and test paths.
    try:
        display_output = str(OUTPUT.relative_to(ROOT))
    except ValueError:
        display_output = str(OUTPUT)
    print(json.dumps({"rows": len(rows), "sha256": digest, "output": display_output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
