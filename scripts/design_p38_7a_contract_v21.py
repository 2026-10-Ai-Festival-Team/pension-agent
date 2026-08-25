"""Build the P38-7A v2.1 semantic-parser design artifact.

This is design-only: it reads the frozen P38-6A attribution and records how a
future parser contract must handle every mismatch.  It never calls HCX and it
does not alter the v2 parser, prompt, ontology, composer, candidate, or gold.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/p38_6a_semantic_contract_attribution.json"
OUTPUT = ROOT / "evaluation/p38_7a_semantic_contract_v21_design.json"


# Human design decisions for the frozen questions. These are a design audit,
# not executable question-ID rules. Every item is explained by a reusable
# contract rule in the generated artifact.
QUESTION_CONTROLS = {
    "P38-2-001": ("derive_comparison", (), ()),
    "P38-2-002": ("retain_essential_qualifier", ("before_retirement",), ()),
    "P38-2-003": ("canonical_subject_scope", ("system:retirement_pension",), ("account:general",)),
    "P38-2-004": ("derive_comparison", ("combined_limit",), ("in_kind",)),
    "P38-2-005": ("canonical_subject_scope", ("account:pension", "not_tax_exempt"), ("system:retirement_pension",)),
    "P38-2-006": ("canonical_subject_scope", ("account:pension",), ("account:ISA",)),
    "P38-2-007": ("canonical_subject_scope", ("account:IRP",), ("event:retirement_benefit",)),
    "P38-2-008": ("directional_transfer", ("account:pension", "additional_credit", "account:ISA->account:pension"), ("system:retirement_pension", "account:ISA->system:retirement_pension")),
    "P38-2-009": ("field_and_qualifier_precision", ("application_route", "transfer_definition", "in_kind"), ("event:retirement_benefit", "procedure", "before_retirement")),
    "P38-2-010": ("precision_only", (), ("product:foreign_etf",)),
    "P38-2-011": ("retain_essential_qualifier", ("change_possibility",), ()),
    "P38-2-012": ("no_change", (), ()),
    "P38-2-013": ("precision_only", (), ("current",)),
    "P38-2-014": ("derive_comparison", (), ()),
    "P38-2-015": ("derive_comparison", (), ("risk_grade_changeability",)),
    "P38-2-016": ("derive_comparison", (), ()),
    "P38-2-017": ("directional_transfer", ("tax_timing_on_transfer",), ("event:retirement_benefit", "current")),
    "P38-2-018": ("field_and_qualifier_precision", ("partial_withdrawal_tax", "account_closure_tax"), ("event:retirement_benefit",)),
}


CONTRACT_RULES = {
    "canonical_subject_scope": {
        "rule": "Account and system scopes remain distinct. A pension account is `account:pension`; it must not be broadened to `system:retirement_pension`.",
        "parser_boundary": "HCX selects a canonical subject only; the validator rejects a scope substitute rather than treating it as an equivalent subject.",
    },
    "derive_comparison": {
        "rule": "Generic comparison is not an HCX relation output. When a deterministic comparison-intent predicate is true and the plan has at least two subjects, the composer derives comparison.",
        "parser_boundary": "The v2.1 schema permits directional transfer relations only; it does not ask HCX to repeat comparison endpoints already represented by subjects.",
    },
    "directional_transfer": {
        "rule": "A transfer whose source and destination change the evidence scope remains explicit. Both endpoints belong only in a directional transfer relation, not duplicated as loose subjects.",
        "parser_boundary": "HCX must emit source and destination for transfer; deterministic validation verifies both are canonical and directionally complete.",
    },
    "retain_essential_qualifier": {
        "rule": "A qualifier stays mandatory only when removing it changes the factual evidence or answer, including before-retirement and change possibility.",
        "parser_boundary": "Prompt examples and the validator preserve only essential qualifiers; the composer continues to use them in requirement identity.",
    },
    "field_and_qualifier_precision": {
        "rule": "The parser emits the exact requested factual fields and evidence-changing qualifiers. Generic `procedure` cannot replace application route or transfer definition; partial withdrawal and account closure taxes stay separate fields.",
        "parser_boundary": "No field is inferred merely because it is related to a selected field. The prompt explicitly instructs empty arrays for unasked distinctions.",
    },
    "precision_only": {
        "rule": "Do not emit a plausible but unasked subject, field, or qualifier. The parser is precision-first and must return no atom when the question does not require the distinction.",
        "parser_boundary": "The prompt prohibits helpful additions and validator/composer preserve only emitted, ontology-valid atoms.",
    },
    "no_change": {
        "rule": "No contract defect was attributed for this frozen question.",
        "parser_boundary": "Retain the v2 semantics; no question-specific behavior is introduced.",
    },
}


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = []
    accounted = Counter()
    for row in source["rows"]:
        qid = row["question_id"]
        control, retain, forbid = QUESTION_CONTROLS[qid]
        mismatches = row["mismatches"]
        owners = Counter(item["owner"] for item in mismatches)
        accounted.update(owners)
        rows.append({
            "question_id": qid,
            "question": row["question"],
            "frozen_semantic_status": row["semantic_status"],
            "v21_control": control,
            "must_preserve": list(retain),
            "must_not_add": list(forbid),
            "frozen_owner_counts": dict(sorted(owners.items())),
        })

    expected = source["mismatch_attribution"]
    if dict(sorted(accounted.items())) != dict(sorted((key, value) for key, value in expected.items() if value)):
        raise RuntimeError("P38-7A design does not account for every frozen P38-6A mismatch")

    result = {
        "experiment": "P38-7A Semantic Parser v2.1 Design",
        "status": "design_only",
        "frozen_boundary": {
            "hcx_calls": 0,
            "p38_6_source_result_modified": False,
            "v2_parser_prompt_ontology_composer_modified": False,
            "candidate_retrieval_policy_modified": False,
            "gold_modified": False,
        },
        "v21_contract": {
            "hcx_output": ["subjects", "fields", "essential_qualifiers", "directional_transfer_relations"],
            "not_hcx_output": ["generic_comparison_relation", "answer", "retrieval_query", "citation", "factual_value"],
            "deterministic_derivations": [
                "lexical entity aliases before HCX",
                "canonical subject-scope validation",
                "generic comparison only when comparison intent and at least two subjects are both present",
                "requirement composition from validated subject, field, qualifier, and directional transfer relation",
            ],
            "precision_contract": "Emit only factual distinctions explicitly or semantically requested by the user. Do not add related fields, qualifiers, scopes, products, events, or future-change concepts.",
        },
        "reusable_rules": CONTRACT_RULES,
        "frozen_mismatch_accounting": dict(sorted(accounted.items())),
        "question_design_mapping": rows,
        "next_gate": {
            "phase": "P38-7B",
            "scope": "Frozen P38-2 dev subset only; isolated HCX semantic parser v2.1 A/B.",
            "success_signals": ["meaning_lost materially below 11/18", "unsupported extras materially below 16 diagnostic mismatches", "directional transfer endpoints retained", "no candidate integration"],
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": len(rows), "mismatch_accounting": result["frozen_mismatch_accounting"], "hcx_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
