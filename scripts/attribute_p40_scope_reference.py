"""Attribute frozen P40 scope/reference outcomes without HCX calls."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUT = ROOT / "evaluation/p40_scope_reference_holdout.json"
OUTPUT = ROOT / "evaluation/p40a_scope_reference_attribution.json"


def main() -> None:
    result = json.loads(INPUT.read_text(encoding="utf-8"))
    details = {item["id"]: item for item in result["scope_metrics"]["details"]}
    outputs = {item["id"]: item for item in result["outputs"]}

    rows = []
    for question_id in ("P40-005", "P40-009"):
        detail, output = details[question_id], outputs[question_id]
        if question_id == "P40-005":
            rows.append(
                {
                    "id": question_id,
                    "question": "KR5114420022와 KR5114450222를 비교할 때 그 상품의 위험등급은 무엇인가요?",
                    "primary_owner": "ambiguity_detection_miss",
                    "secondary_effect": "binder_scope_expansion",
                    "trace": {
                        "explicit_subjects": output["resolution"]["explicit_subjects"],
                        "reference_expression": "그 상품",
                        "resolver_unresolved_references": output["resolution"]["unresolved_references"],
                        "binder_status": [item["status"] for item in output["binding"]["bindings"]],
                    },
                    "finding": "The anaphora recognizer covers '그 계좌' and '그 제도' but not '그 상품'. The resolver therefore emits no unresolved reference, allowing the binder to produce a two-product comparison binding.",
                    "safe_expected_behavior": "multiple candidates + singular anaphora + no ordinal/disambiguating cue -> unresolved",
                    "hcx_calls": 0,
                }
            )
        else:
            rows.append(
                {
                    "id": question_id,
                    "question": "사용자가 매년 임금 기준으로 부담금을 넣는 제도는 무엇이고, 그 계좌의 운용방법은 누가 선택하나요?",
                    "primary_owner": "resolver_antecedent_unavailable",
                    "final_pipeline_behavior": "safe_selector_anchored_binding",
                    "trace": {
                        "resolver_unresolved_references": output["resolution"]["unresolved_references"],
                        "selected_requirements": output["selected_requirements"],
                        "binding_active_subjects": output["binding"]["active_subjects"],
                        "binding_status": [item["status"] for item in output["binding"]["bindings"]],
                    },
                    "finding": "The raw resolver has no explicit account antecedent. The selector returns only DC-scoped requirements, so the binder anchors DC without fabricating any requirement. This is safe final behavior, but should not be counted as standalone resolver success.",
                    "hcx_calls": 0,
                }
            )

    payload = {
        "experiment": "P40-A Scope/Reference Attribution",
        "input_result": str(INPUT.relative_to(ROOT)),
        "hcx_calls": 0,
        "attributions": rows,
        "decision": {
            "primary_blocker": "P40-005 ambiguity_detection_miss",
            "candidate_integration": "prohibited",
            "next_fix_boundary": "generalized singular-anaphora ambiguity rule in resolver; binder must preserve unresolved output",
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hcx_calls": 0, "primary_blocker": payload["decision"]["primary_blocker"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
