"""P38-6A frozen-attribution only; never call or modify HCX/parser/contract."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/p38_6_v2_ab_p38_2_subset.json"
OUTPUT = ROOT / "evaluation/p38_6a_semantic_contract_attribution.json"


def _relation(value: dict) -> str:
    return "|".join([value["type"], value.get("source") or "", value.get("destination") or "", value.get("left") or "", value.get("right") or ""])


# Frozen reviewer attribution for every component set-difference. This data is
# diagnostic metadata, never executable parser logic or a score correction.
R = {
 "P38-2-001": [("relation","gold_only","comparison||||","contract_equivalent","Both explicit subjects and both factual fields remain; an absent generic comparison relation changes no evidence scope.")],
 "P38-2-002": [("qualifier","gold_only","before_retirement","real_semantic_miss","Early withdrawal selects a narrower evidence set than generic withdrawal.")],
 "P38-2-003": [("subject","gold_only","system:retirement_pension","real_semantic_miss","The question is retirement-pension participant education, not a general investment account."),("subject","prediction_only","account:general","unsupported_extra","A general-account scope is absent from the question.")],
 "P38-2-004": [("qualifier","gold_only","combined_limit","real_semantic_miss","Individual and combined tax-credit limits are different factual scopes."),("qualifier","prediction_only","in_kind","unsupported_extra","No in-kind transfer condition appears in the question."),("relation","gold_only","comparison||||","relation_representation_mismatch","The two account subjects preserve comparison inputs, although the relation itself was omitted.")],
 "P38-2-005": [("subject","gold_only","account:pension","real_semantic_miss","A pension account and the retirement-pension system are not interchangeable tax scopes."),("subject","prediction_only","system:retirement_pension","unsupported_extra","The broader retirement-pension system was not requested."),("qualifier","gold_only","not_tax_exempt","real_semantic_miss","Whether tax disappears is an explicit factual question beyond tax timing."),("relation","gold_only","comparison||||","relation_representation_mismatch","The paired account comparison is implicit in subjects but not explicitly represented.")],
 "P38-2-006": [("subject","gold_only","account:pension","real_semantic_miss","Pension-account tax treatment cannot be replaced with ISA treatment."),("subject","prediction_only","account:ISA","unsupported_extra","ISA is not in the question."),("relation","gold_only","comparison||||","relation_representation_mismatch","Comparison structure is omitted, although the principal loss is the wrong account scope.")],
 "P38-2-007": [("subject","gold_only","account:IRP","real_semantic_miss","IRP withdrawal rules cannot be recovered from a retirement-benefit event."),("subject","prediction_only","event:retirement_benefit","unsupported_extra","Retirement-benefit event scope is not requested."),("relation","gold_only","comparison||||","relation_representation_mismatch","The comparison relation is absent after IRP scope was lost.")],
 "P38-2-008": [("subject","gold_only","account:pension","real_semantic_miss","The destination must be a pension account, not the broad retirement-pension system."),("subject","prediction_only","system:retirement_pension","unsupported_extra","The system-level subject over-broadens the destination scope."),("qualifier","gold_only","additional_credit","real_semantic_miss","The special additional credit is distinct from a generic tax-credit limit."),("relation","gold_only","transfer|account:ISA|account:pension||","real_semantic_miss","ISA-to-pension-account direction and destination are factual requirements."),("relation","prediction_only","transfer|account:ISA|system:retirement_pension||","unsupported_extra","The predicted transfer destination is not the requested account scope.")],
 "P38-2-009": [("subject","prediction_only","event:retirement_benefit","unsupported_extra","A retirement-benefit event is not asked for."),("field","gold_only","application_route","real_semantic_miss","Where DB/DC and IRP users apply is a requested factual field."),("field","gold_only","transfer_definition","real_semantic_miss","Not selling the fund describes a specific transfer form, not generic procedure."),("field","prediction_only","procedure","unsupported_extra","A generic procedure field does not answer the route/transfer-form questions."),("qualifier","gold_only","in_kind","real_semantic_miss","Keeping the fund unsold is an evidence-changing in-kind condition."),("qualifier","prediction_only","before_retirement","unsupported_extra","Being an active worker is not early withdrawal."),("relation","gold_only","comparison||||","relation_representation_mismatch","The requested DB/DC/IRP route contrast is omitted."),("relation","prediction_only","transfer|||event:retirement_benefit|","unsupported_extra","This malformed transfer relation is unsupported by the question.")],
 "P38-2-010": [("subject","prediction_only","product:foreign_etf","unsupported_extra","The question asks generic ETF restrictions in the retirement-pension system, not foreign ETF scope.")],
 "P38-2-011": [("qualifier","gold_only","change_possibility","real_semantic_miss","Future risk-grade changeability is explicitly requested." )],
 "P38-2-012": [],
 "P38-2-013": [("qualifier","prediction_only","current","unsupported_extra","Current timing is not a requested distinction in the annual-fee versus three-year cost question.")],
 "P38-2-014": [("relation","gold_only","comparison||||","relation_representation_mismatch","Gold uses an endpoint-free comparison relation."),("relation","prediction_only","comparison|||product:KR5114420022|product:KR5114450222","relation_representation_mismatch","Prediction supplies endpoints already present as subjects; factual comparison meaning is preserved.")],
 "P38-2-015": [("field","prediction_only","risk_grade_changeability","unsupported_extra","Past-versus-current grade is not a future-changeability request."),("relation","gold_only","comparison||||","contract_equivalent","Both product subjects plus current/historical grade preserve the factual comparison without an explicit relation.")],
 "P38-2-016": [("relation","gold_only","comparison||||","relation_representation_mismatch","Gold has endpoint-free comparison."),("relation","prediction_only","comparison|||account:DB|account:DC","relation_representation_mismatch","Prediction supplies the same DB/DC endpoints already held in subjects.")],
 "P38-2-017": [("subject","prediction_only","event:retirement_benefit","contract_granularity_mismatch","The event is already encoded as transfer source; emitting it as a subject duplicates the same semantic context."),("qualifier","gold_only","tax_timing_on_transfer","real_semantic_miss","The question asks tax timing specifically after the retirement-benefit-to-IRP transfer."),("qualifier","prediction_only","current","unsupported_extra","Current timing is not requested.")],
 "P38-2-018": [("subject","prediction_only","event:retirement_benefit","unsupported_extra","No retirement-benefit event appears in the partial-withdrawal versus closure question."),("field","gold_only","account_closure_tax","real_semantic_miss","Closure tax treatment is distinct from partial-withdrawal tax treatment."),("field","gold_only","partial_withdrawal_tax","real_semantic_miss","Partial-withdrawal tax treatment is explicitly required and cannot be inferred from conditions alone.")],
}

TAXONOMY = (
    "contract_equivalent", "contract_granularity_mismatch", "relation_representation_mismatch",
    "real_semantic_miss", "unsupported_extra", "ontology_ambiguity", "gold_contract_issue",
)


STATUS = {
 "P38-2-001": ("fully_preserved", (False, False, False)), "P38-2-002": ("meaning_lost", (True, True, True)),
 "P38-2-003": ("meaning_lost", (True, True, True)), "P38-2-004": ("meaning_lost", (True, True, True)),
 "P38-2-005": ("meaning_lost", (True, True, True)), "P38-2-006": ("meaning_lost", (True, True, True)),
 "P38-2-007": ("meaning_lost", (True, True, True)), "P38-2-008": ("meaning_lost", (True, True, True)),
 "P38-2-009": ("meaning_lost", (True, True, True)), "P38-2-010": ("partially_preserved", (True, False, True)),
 "P38-2-011": ("meaning_lost", (True, True, True)), "P38-2-012": ("fully_preserved", (False, False, False)),
 "P38-2-013": ("partially_preserved", (True, False, True)), "P38-2-014": ("fully_preserved", (False, False, False)),
 "P38-2-015": ("partially_preserved", (True, True, True)), "P38-2-016": ("fully_preserved", (False, False, False)),
 "P38-2-017": ("meaning_lost", (True, True, True)), "P38-2-018": ("meaning_lost", (True, True, True)),
}


def _mismatch_keys(detail: dict):
    keys = []
    for component, key in (("subject", "subjects"), ("field", "fields"), ("qualifier", "essential_qualifiers")):
        gold, predicted = set(detail["gold"][key]), set(detail["predicted"][key])
        keys += [(component, "gold_only", value) for value in sorted(gold - predicted)]
        keys += [(component, "prediction_only", value) for value in sorted(predicted - gold)]
    gold_rel, predicted_rel = {_relation(value) for value in detail["gold"]["relations"]}, {_relation(value) for value in detail["predicted"]["relations"]}
    keys += [("relation", "gold_only", value) for value in sorted(gold_rel - predicted_rel)]
    keys += [("relation", "prediction_only", value) for value in sorted(predicted_rel - gold_rel)]
    return keys


def main() -> None:
    frozen = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows, owners, statuses = [], Counter(), Counter()
    for detail in frozen["metrics"]["details"]:
        qid = detail["source_question_id"]
        actual = _mismatch_keys(detail)
        reviewed = R[qid]
        indexed = {(component, side, value): (owner, reason) for component, side, value, owner, reason in reviewed}
        if set(actual) != set(indexed):
            raise RuntimeError(f"P38-6A review mismatch for {qid}: unreviewed={set(actual)-set(indexed)}, stale={set(indexed)-set(actual)}")
        mismatch_rows = []
        for component, side, value in actual:
            owner, reason = indexed[(component, side, value)]
            owners[owner] += 1
            mismatch_rows.append({
                "component": component,
                "gold": value if side == "gold_only" else None,
                "prediction": value if side == "prediction_only" else None,
                "owner": owner,
                "reason": reason,
            })
        status, effects = STATUS[qid]
        statuses[status] += 1
        rows.append({
            "question_id": qid,
            "question": next(item["question"] for item in _load_gold_rows() if item["source_question_id"] == qid),
            "semantic_status": status,
            "gold": detail["gold"], "prediction": detail["predicted"],
            "gold_requirements": detail["gold_requirements"], "predicted_requirements": detail["predicted_requirements"],
            "mismatches": mismatch_rows,
            "requirement_effect": {"retrieval_scope_changes": effects[0], "answer_changes": effects[1], "evidence_scope_changes": effects[2]},
        })
    result = {
        "experiment": "P38-6A Semantic Contract vs Real Semantic Miss Attribution",
        "frozen_experiment": {"hcx_calls": 0, "parser_modifications": 0, "candidate_modifications": 0, "gold_modifications": 0, "source_result_modified": False},
        "official_frozen_p38_6_metrics": frozen["metrics"],
        "official_runtime": frozen["runtime"],
        "mismatch_attribution": {owner: owners[owner] for owner in TAXONOMY},
        "question_semantic_preservation": dict(sorted(statuses.items())),
        "diagnostic_semantic_preservation": {
            "only_diagnostic_not_official_score": True,
            "fully_preserved": statuses["fully_preserved"],
            "partially_preserved": statuses["partially_preserved"],
            "meaning_lost": statuses["meaning_lost"],
            "finding": "Representation mismatches explain several exact-match failures, but 11/18 questions still lose evidence-changing meaning; contract-only correction cannot rescue the official 35.6% coverage result.",
        },
        "architecture_recommendation": {
            "choice": "C. contract + parser both need redesign",
            "reason": "Endpoint-free comparison gold conflicts with HCX endpoint-bearing relations, while essential qualifiers and account scopes are independently missed or replaced by unsupported atoms.",
            "implemented_in_this_phase": False,
        },
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mismatch_attribution": result["mismatch_attribution"], "question_semantic_preservation": result["question_semantic_preservation"], "hcx_calls": 0}, ensure_ascii=False))


def _load_gold_rows():
    path = ROOT / "question_bank/development/semantic_contract_v2_manual_gold.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
