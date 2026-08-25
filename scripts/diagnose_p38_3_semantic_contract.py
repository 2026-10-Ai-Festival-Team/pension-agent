"""Diagnose P38-3 action/modifier contract failures without invoking HCX.

The review is intentionally explicit and case-level because this is a frozen
developer diagnostic, not executable planner logic.  It separates atoms that
are redundant with a canonical field from atoms that are genuinely required
to preserve the retrieval requirement.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


INPUT = ROOT / "evaluation/p38_3_hcx_semantic_planner_results.json"
QUESTIONS = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout.jsonl"
OUTPUT = ROOT / "evaluation/p38_4_semantic_contract_diagnosis.json"


# Every missing action/modifier is manually reviewed against the original
# Korean question.  This is analysis metadata only: no production path reads
# it.  ``essential`` means dropping that atom loses a factual condition that
# the field/subject set cannot safely recover on its own.
REVIEW: dict[str, dict[str, dict[str, dict[str, object]]]] = {
    "P38-2-001": {
        "missing_actions": {
            "manage": {"owner": "ontology_redundancy", "essential": False, "rationale": "operation_party already names the management fact."},
            "compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "DB+DC subjects and paired fields carry the factual comparison scope."},
        },
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both account subjects are explicit."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The pair of subjects and fields already requires two factual lookups."},
        },
    },
    "P38-2-002": {
        "missing_actions": {"withdraw": {"owner": "ontology_redundancy", "essential": False, "rationale": "withdrawal_reason and required_document encode the operation."}},
        "missing_modifiers": {"before_retirement": {"owner": "prompt_salience_miss", "essential": True, "rationale": "Early withdrawal is narrower than a generic withdrawal query."}},
    },
    "P38-2-003": {
        "missing_actions": {"educate": {"owner": "ontology_redundancy", "essential": False, "rationale": "education_frequency and education_outsourcing identify the education requirement."}},
    },
    "P38-2-004": {
        "missing_actions": {
            "contribute": {"owner": "ontology_redundancy", "essential": False, "rationale": "tax_credit_limit is a contribution-limit field."},
            "compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "The two account scopes are explicit."},
        },
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both account subjects are explicit."},
            "combined_limit": {"owner": "prompt_salience_miss", "essential": True, "rationale": "Individual and combined deduction limits are distinct factual scopes."},
        },
    },
    "P38-2-005": {
        "missing_actions": {
            "receive": {"owner": "ontology_granularity_mismatch", "essential": False, "rationale": "The action label does not precisely express investment-gain taxation; tax_timing is the factual field."},
            "compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "General and pension account subjects express the two scopes."},
        },
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both account subjects are explicit."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The paired account scopes support the comparison."},
            "not_tax_exempt": {"owner": "prompt_salience_miss", "essential": True, "rationale": "The user explicitly asks whether tax disappears, beyond timing alone."},
        },
    },
    "P38-2-006": {
        "missing_actions": {
            "invest": {"owner": "ontology_redundancy", "essential": False, "rationale": "The foreign ETF product subject supplies the investment object."},
            "compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "Two account subjects supply the factual comparison scope."},
        },
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both account subjects are explicit."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The paired account scopes support the comparison."},
        },
    },
    "P38-2-007": {
        "missing_actions": {"compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "The two account subjects and shared fields imply comparison."}},
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both account subjects are explicit."},
            "before_retirement": {"owner": "prompt_salience_miss", "essential": True, "rationale": "The 55-before condition narrows withdrawal evidence."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The two account subjects and shared fields imply comparison."},
        },
        "extra_actions": {"educate": {"owner": "semantic_inference_failure", "rationale": "No education meaning appears in the question."}},
    },
    "P38-2-008": {
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "ISA and pension account subjects are explicit."},
            "additional_credit": {"owner": "prompt_salience_miss", "essential": True, "rationale": "The question asks for the special additional credit, not the generic limit."},
            "maturity_event": {"owner": "prompt_salience_miss", "essential": True, "rationale": "The transfer deadline is conditional on ISA maturity."},
        },
    },
    "P38-2-009": {
        "missing_actions": {"compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "The DB/DC/IRP subjects already require separate routing facts."}},
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "DB, DC, and IRP scopes are explicit."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The subject list retains the route comparison scope."},
            "in_kind": {"owner": "prompt_salience_miss", "essential": True, "rationale": "Not selling the fund is a distinct in-kind transfer condition."},
        },
        "extra_modifiers": {"before_retirement": {"owner": "semantic_inference_failure", "rationale": "Being a current worker is not an early-withdrawal condition."}},
    },
    "P38-2-010": {
        "missing_actions": {"invest": {"owner": "ontology_redundancy", "essential": False, "rationale": "ETF trading restrictions are already encoded by the requested fields."}},
    },
    "P38-2-011": {
        "missing_actions": {"invest": {"owner": "ontology_redundancy", "essential": False, "rationale": "A product risk-grade field does not require an independent invest action."}},
    },
    "P38-2-012": {
        "missing_actions": {"invest": {"owner": "ontology_redundancy", "essential": False, "rationale": "Product tracking-index and allocation fields identify the factual request."}},
    },
    "P38-2-013": {
        "missing_actions": {"invest": {"owner": "ontology_redundancy", "essential": False, "rationale": "The product fee fields already define the request."}},
        "missing_modifiers": {
            "annual_rate": {"owner": "ontology_redundancy", "essential": False, "rationale": "total_fee canonically represents the annual fee rate."},
            "holding_period": {"owner": "ontology_redundancy", "essential": False, "rationale": "cost_example canonically represents a period-specific example."},
            "field_boundary": {"owner": "ontology_redundancy", "essential": False, "rationale": "The total_fee plus cost_example pair expresses the requested distinction."},
        },
    },
    "P38-2-014": {
        "missing_actions": {"compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "The response retained both product subjects and comparison modifier."}},
        "missing_modifiers": {"relative_low_risk": {"owner": "ontology_granularity_mismatch", "essential": False, "rationale": "Comparing the two risk_grade values yields this relation; it is not an independent evidence field."}},
    },
    "P38-2-015": {
        "missing_modifiers": {
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "Both product subjects are retained."},
            "historical": {"owner": "gold_contract_issue", "essential": True, "rationale": "Historical was required by gold but deliberately absent from the P38-3 enum schema."},
        },
        "extra_modifiers": {"change_possibility": {"owner": "semantic_inference_failure", "rationale": "Past-versus-current comparison was misread as future change possibility."}},
    },
    "P38-2-016": {
        "missing_actions": {
            "manage": {"owner": "ontology_redundancy", "essential": False, "rationale": "operation_party encodes the management fact."},
            "compare": {"owner": "ontology_redundancy", "essential": False, "rationale": "DB and DC subjects supply the requested contrast."},
        },
        "missing_modifiers": {
            "account_specific": {"owner": "ontology_redundancy", "essential": False, "rationale": "DB and DC are explicit subjects."},
            "comparison": {"owner": "ontology_redundancy", "essential": False, "rationale": "The two account subjects supply the contrast."},
        },
    },
    "P38-2-017": {
        "missing_actions": {"transfer": {"owner": "prompt_salience_miss", "essential": True, "rationale": "Tax timing is specifically conditioned on moving retirement pay into IRP."}},
    },
    "P38-2-018": {
        "missing_actions": {
            "withdraw": {"owner": "ontology_redundancy", "essential": False, "rationale": "withdrawal_reason and tax_treatment encode the withdrawal subject matter."},
            "compare": {"owner": "ontology_granularity_mismatch", "essential": True, "rationale": "The ontology has no separate close-account operation for the second side of the comparison."},
        },
        "missing_modifiers": {"comparison": {"owner": "ontology_granularity_mismatch", "essential": True, "rationale": "Partial withdrawal versus full closure needs an operation-pair representation, not only a generic comparison flag."}},
    },
}


def _load_questions() -> dict[str, str]:
    rows = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["source_question_id"]: row["question"] for row in rows}


def _review_atoms(qid: str, kind: str, atoms: list[str]) -> list[dict]:
    reviews = REVIEW.get(qid, {}).get(kind, {})
    missing = set(atoms) - set(reviews)
    extra = set(reviews) - set(atoms)
    if missing or extra:
        raise RuntimeError(f"Incomplete P38-4 review for {qid}/{kind}: missing={sorted(missing)}, extra={sorted(extra)}")
    return [{"atom": atom, **reviews[atom]} for atom in sorted(atoms)]


def main() -> None:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    questions = _load_questions()
    rows = []
    owner_counts: Counter[str] = Counter()
    essential_missing = 0
    redundant_missing = 0
    for detail in source["metrics"]["details"]:
        qid = detail["source_question_id"]
        gold, predicted = detail["gold"], detail["predicted"]
        missing_actions = sorted(set(gold["actions"]) - set(predicted["actions"]))
        extra_actions = sorted(set(predicted["actions"]) - set(gold["actions"]))
        missing_modifiers = sorted(set(gold["modifiers"]) - set(predicted["modifiers"]))
        extra_modifiers = sorted(set(predicted["modifiers"]) - set(gold["modifiers"]))
        reviewed = {
            "missing_actions": _review_atoms(qid, "missing_actions", missing_actions),
            "extra_actions": _review_atoms(qid, "extra_actions", extra_actions),
            "missing_modifiers": _review_atoms(qid, "missing_modifiers", missing_modifiers),
            "extra_modifiers": _review_atoms(qid, "extra_modifiers", extra_modifiers),
        }
        all_reviewed = [item for values in reviewed.values() for item in values]
        owner_counts.update(item["owner"] for item in all_reviewed)
        essential = [item for item in reviewed["missing_actions"] + reviewed["missing_modifiers"] if item["essential"]]
        essential_missing += len(essential)
        redundant_missing += sum(item["owner"] == "ontology_redundancy" for item in reviewed["missing_actions"] + reviewed["missing_modifiers"])
        rows.append({
            "source_question_id": qid,
            "question": questions[qid],
            "gold": {key: gold[key] for key in ("subjects", "actions", "fields", "modifiers")},
            "hcx": {key: predicted[key] for key in ("subjects", "actions", "fields", "modifiers")},
            "field_exact": set(gold["fields"]) == set(predicted["fields"]),
            "action_modifier_review": reviewed,
            "semantic_loss_from_missing_action_or_modifier": bool(essential),
            "non_contract_atom_errors": {
                "missing_subjects": sorted(set(gold["subjects"]) - set(predicted["subjects"])),
                "extra_subjects": sorted(set(predicted["subjects"]) - set(gold["subjects"])),
                "missing_fields": sorted(set(gold["fields"]) - set(predicted["fields"])),
                "extra_fields": sorted(set(predicted["fields"]) - set(gold["fields"])),
            },
        })

    total = len(rows)
    result = {
        "experiment": "P38-4 Semantic Contract Diagnosis",
        "input_artifact": str(INPUT.relative_to(ROOT)),
        "hcx_calls": 0,
        "candidate_agent_changed": False,
        "purpose": "Frozen-artifact contract review; it does not modify or re-score the P38-3 feasibility result.",
        "summary": {
            "question_count": total,
            "field_exact": sum(row["field_exact"] for row in rows),
            "missing_action_modifier_atoms": sum(
                len(row["action_modifier_review"][kind])
                for row in rows for kind in ("missing_actions", "missing_modifiers")
            ),
            "essential_missing_action_modifier_atoms": essential_missing,
            "ontology_redundant_missing_atoms": redundant_missing,
            "questions_with_semantic_loss_from_action_modifier": sum(row["semantic_loss_from_missing_action_or_modifier"] for row in rows),
            "owner_counts": dict(sorted(owner_counts.items())),
        },
        "interpretation": {
            "action_contract": "Most missing actions duplicate a field-specific operation and should not alone fail semantic requirement coverage.",
            "modifier_contract": "Some missing modifiers are essential factual qualifiers (for example early withdrawal, combined limit, ISA maturity, and in-kind transfer); others duplicate field or subject structure.",
            "requirement_exact": "The P38-3 0/18 exact score is overly sensitive to redundant action/modifier atom mismatches and must not be treated as pure semantic-inference failure.",
        },
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
