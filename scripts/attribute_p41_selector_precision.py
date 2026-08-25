"""Attribute frozen P41 selector precision failures without HCX calls."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUT = ROOT / "evaluation/p41_scope_requirement_holdout.json"
OUTPUT = ROOT / "evaluation/p41a_selector_precision_attribution.json"


def main() -> None:
    result = json.loads(INPUT.read_text(encoding="utf-8"))
    requirement_details = {item["source_question_id"]: item for item in result["requirement_metrics"]["details"]}
    scope_details = {item["id"]: item for item in result["scope_metrics"]["details"]}
    rows = []
    for question_id, owner, fix_boundary in (
        ("P41-008", "selector_scope_expansion", "resolver-first scope restriction requires an indirect DC subject resolver; current raw resolver leaves DB/DC plural"),
        ("P41-010", "selector_scope_expansion", "resolver-first scope restriction can present only IRP-scoped requirements because ordinal account resolution is already deterministic"),
        ("P41-011", "selector_extra_requirement", "scope restriction alone is insufficient; DC.operation_party is in-scope but not requested"),
    ):
        requirement, scope = requirement_details[question_id], scope_details[question_id]
        rows.append({
            "id": question_id,
            "primary_owner": owner,
            "question": requirement["question"],
            "gold_requirements": requirement["gold_requirements"],
            "predicted_requirements": requirement["predicted_requirements"],
            "unsupported_extra_requirements": requirement["unsupported_extra_requirements"],
            "raw_active_subjects": scope["raw_active_subjects"],
            "effective_bound_subjects": scope["effective_bound_subjects"],
            "binder_behavior": scope["binding"],
            "fix_boundary": fix_boundary,
        })
    payload = {
        "experiment": "P41-A Selector Scope/Precision Attribution",
        "input_result": str(INPUT.relative_to(ROOT)),
        "hcx_calls": 0,
        "attributions": rows,
        "architecture_findings": {
            "p41_010": "The resolver can narrow IRP before selection, but the current execution calls the selector without that scope input.",
            "p41_008": "Scope cannot be restricted safely until the resolver also understands the indirect '가입자가 직접 운용방법을 정하는 쪽' closed-pair predicate.",
            "p41_011": "An active-subject enum restriction cannot remove extra requirements belonging to the active subject; selector precision remains a separate contract.",
        },
        "decision": "Do not patch individual P41 questions. Design a resolver-first, subject-filtered selector contract plus an independent no-extra-requirement precision contract.",
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hcx_calls": 0, "owners": [item["primary_owner"] for item in rows]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
