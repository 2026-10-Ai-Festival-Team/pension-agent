"""Freeze manual P38-5 semantic-contract-v2 gold; never convert v1 atoms.

The mappings below were reviewed from question text under the v2 contract.
The script reads source files only to copy frozen question text and verify
coverage; it never reads v1 action/field/modifier labels for conversion.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.semantic_contract_v2 import (
    RequirementComposerV2,
    SemanticPlanV2,
    SemanticRelation,
    SemanticContractV2Validator,
)


P38_1 = ROOT / "question_bank/development/semantic_atoms_v1.jsonl"
P38_2 = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout.jsonl"
OUTPUT = ROOT / "question_bank/development/semantic_contract_v2_manual_gold.jsonl"
METADATA = ROOT / "question_bank/development/semantic_contract_v2_manual_gold_metadata.json"


def _plan(subjects, fields, qualifiers=(), relations=()):
    return SemanticPlanV2(tuple(subjects), tuple(fields), tuple(qualifiers), tuple(relations))


def _comparison(left=None, right=None):
    return SemanticRelation("comparison", left=left, right=right)


def _transfer(source, destination):
    return SemanticRelation("transfer", source=source, destination=destination)


# Explicit manual v2 annotations.  They are assigned by source question ID
# after reading each Korean question, not generated from its v1 atom labels.
MANUAL_PLANS: dict[str, SemanticPlanV2] = {
    # P38-1 development rows
    "P36-001": _plan(("account:DB", "account:DC"), ("operation_party", "benefit_determination", "contribution_structure"), relations=(_comparison(),)),
    "P37-001": _plan(("account:DB", "account:DC"), ("operation_party", "benefit_determination", "contribution_structure"), relations=(_comparison(),)),
    "P36-002": _plan(("system:retirement_pension",), ("education_provider", "education_frequency", "education_outsourcing")),
    "P37-002": _plan(("system:retirement_pension",), ("education_provider", "education_frequency", "education_outsourcing")),
    "P36-003": _plan(("account:DC", "account:IRP"), ("etf_direct_trade", "leverage_inverse_restriction")),
    "P37-011": _plan(("system:retirement_pension",), ("etf_direct_trade", "leverage_inverse_restriction")),
    "P36-004": _plan(("account:pension_savings", "account:IRP"), ("tax_credit_limit",), ("combined_limit",), (_comparison(),)),
    "P37-004": _plan(("account:pension_savings", "account:IRP"), ("tax_credit_limit",), ("combined_limit",), (_comparison(),)),
    "P36-005": _plan(("account:general", "account:pension"), ("tax_timing",), ("not_tax_exempt",), (_comparison(),)),
    "P37-005": _plan(("account:general", "account:pension"), ("tax_timing",), ("not_tax_exempt",), (_comparison(),)),
    "P36-006": _plan(("product:foreign_etf", "account:general", "account:pension"), ("tax_timing",), relations=(_comparison(),)),
    "P37-006": _plan(("product:foreign_etf", "account:general", "account:pension"), ("tax_timing",), relations=(_comparison(),)),
    "P36-007": _plan(("account:pension_savings", "account:IRP"), ("withdrawal_reason", "tax_treatment"), ("before_retirement",), (_comparison(),)),
    "P37-007": _plan(("account:pension_savings", "account:IRP"), ("withdrawal_reason", "tax_treatment"), ("before_retirement",), (_comparison(),)),
    "P36-008": _plan(("account:DC",), ("withdrawal_reason", "required_document", "procedure"), ("before_retirement",)),
    "P37-008": _plan(("account:DC",), ("withdrawal_reason", "required_document", "procedure"), ("before_retirement",)),
    "P36-009": _plan(("account:ISA", "account:pension"), ("transfer_deadline", "tax_credit_limit"), ("isa_maturity", "additional_credit"), (_transfer("account:ISA", "account:pension"),)),
    "P37-009": _plan(("account:ISA", "account:pension"), ("transfer_deadline", "tax_credit_limit"), ("isa_maturity", "additional_credit"), (_transfer("account:ISA", "account:pension"),)),
    "P36-010": _plan(("account:DB", "account:DC", "account:IRP"), ("transfer_definition", "application_route"), ("in_kind",), (_comparison(),)),
    "P37-010": _plan(("account:DB", "account:DC", "account:IRP"), ("transfer_definition", "application_route"), ("in_kind",), (_comparison(),)),
    "P36-013": _plan(("product:KR510902773M",), ("risk_grade", "risk_grade_changeability"), ("current", "change_possibility")),
    "P37-013": _plan(("product:KR510902773M",), ("risk_grade", "risk_grade_changeability"), ("current", "change_possibility")),
    "P36-014": _plan(("product:KR5127450215",), ("tracking_index", "equity_allocation_limit")),
    "P37-014": _plan(("product:KR5127450215",), ("tracking_index", "equity_allocation_limit")),
    "P36-015": _plan(("product:KR510902773M",), ("total_fee", "cost_example")),
    "P37-015": _plan(("product:KR510902773M",), ("total_fee", "cost_example")),
    "P36-017": _plan(("product:KR5114420022", "product:KR5114450222"), ("risk_grade",), relations=(_comparison(),)),
    "P37-017": _plan(("product:KR5114420022", "product:KR5114450222"), ("risk_grade",), relations=(_comparison(),)),
    "P36-018": _plan(("product:KR5120420039", "product:KR5120420091"), ("risk_grade",), relations=(_comparison(),)),
    "P37-012": _plan(("account:DB", "account:DC"), ("operation_party", "benefit_determination"), relations=(_comparison(),)),
    # P38-2 became developer data after P38-3/P38-4 and is manually reviewed
    # again here under the v2 contract.
    "P38-2-001": _plan(("account:DB", "account:DC"), ("operation_party", "benefit_determination"), relations=(_comparison(),)),
    "P38-2-002": _plan(("account:DC",), ("withdrawal_reason", "required_document"), ("before_retirement",)),
    "P38-2-003": _plan(("system:retirement_pension",), ("education_frequency", "education_outsourcing")),
    "P38-2-004": _plan(("account:pension_savings", "account:IRP"), ("tax_credit_limit",), ("combined_limit",), (_comparison(),)),
    "P38-2-005": _plan(("account:general", "account:pension"), ("tax_timing",), ("not_tax_exempt",), (_comparison(),)),
    "P38-2-006": _plan(("product:foreign_etf", "account:general", "account:pension"), ("tax_timing",), relations=(_comparison(),)),
    "P38-2-007": _plan(("account:pension_savings", "account:IRP"), ("withdrawal_reason", "tax_treatment"), ("before_retirement",), (_comparison(),)),
    "P38-2-008": _plan(("account:ISA", "account:pension"), ("transfer_deadline", "tax_credit_limit"), ("isa_maturity", "additional_credit"), (_transfer("account:ISA", "account:pension"),)),
    "P38-2-009": _plan(("account:DB", "account:DC", "account:IRP"), ("transfer_definition", "application_route"), ("in_kind",), (_comparison(),)),
    "P38-2-010": _plan(("system:retirement_pension",), ("etf_direct_trade", "leverage_inverse_restriction")),
    "P38-2-011": _plan(("product:KR510902773M",), ("risk_grade", "risk_grade_changeability"), ("current", "change_possibility")),
    "P38-2-012": _plan(("product:KR5127450215",), ("tracking_index", "equity_allocation_limit")),
    "P38-2-013": _plan(("product:KR510902773M",), ("total_fee", "cost_example")),
    "P38-2-014": _plan(("product:KR5114420022", "product:KR5114450222"), ("risk_grade",), relations=(_comparison(),)),
    "P38-2-015": _plan(("product:KR5120420039", "product:KR5120420091"), ("risk_grade",), ("current", "historical"), (_comparison(),)),
    "P38-2-016": _plan(("account:DB", "account:DC"), ("contribution_structure", "operation_party"), relations=(_comparison(),)),
    "P38-2-017": _plan(("account:IRP",), ("tax_timing",), ("tax_timing_on_transfer",), (_transfer("event:retirement_benefit", "account:IRP"),)),
    "P38-2-018": _plan(("account:pension",), ("partial_withdrawal_condition", "account_closure_condition", "partial_withdrawal_tax", "account_closure_tax"), relations=(_comparison("partial_withdrawal", "account_closure"),)),
}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build() -> tuple[list[dict], dict]:
    source_rows = [("p38_1_development", row) for row in _rows(P38_1)] + [("p38_2_development_after_execution", row) for row in _rows(P38_2)]
    source_ids = [row["source_question_id"] for _, row in source_rows]
    if len(source_ids) != len(set(source_ids)):
        raise RuntimeError("P38-5 source IDs must be unique")
    if set(source_ids) != set(MANUAL_PLANS):
        raise RuntimeError(f"P38-5 manual coverage mismatch: source_only={sorted(set(source_ids) - set(MANUAL_PLANS))}, manual_only={sorted(set(MANUAL_PLANS) - set(source_ids))}")
    output = []
    for split, source in source_rows:
        qid = source["source_question_id"]
        plan = MANUAL_PLANS[qid]
        errors = SemanticContractV2Validator.validate(plan)
        if errors:
            raise RuntimeError(f"{qid} has unknown v2 ontology values: {errors}")
        output.append({
            "id": f"V2-{qid}",
            "source_question_id": qid,
            "source_split": split,
            "question": source["question"],
            "subjects": list(plan.subjects),
            "fields": list(plan.fields),
            "essential_qualifiers": list(plan.qualifiers),
            "relations": [relation.__dict__ for relation in plan.relations],
            "requirements": list(RequirementComposerV2.compose(plan)),
            "annotation_status": "confirmed",
            "annotation_source": "manual",
            "legacy_v1_used_as_reference": True,
            "auto_converted": False,
            "ambiguity": None,
        })
    canonical = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    metadata = {
        "name": "P38-5 Manual Semantic Contract v2 Gold",
        "question_count": len(output),
        "annotation_status_counts": {"confirmed": len(output), "needs_annotation": 0, "ambiguous": 0},
        "auto_converted_count": 0,
        "unknown_ontology_value_count": 0,
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "hcx_calls": 0,
        "candidate_agent_changed": False,
    }
    return output, metadata


def main() -> None:
    rows, metadata = build()
    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
