"""Build the P49-2H-3F 700-record host-owned semantic request manifest.

No question text, completion, or HCX call is produced here.  Each row fixes
the semantic scope that a later Structured Output question must express.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_v1.jsonl"
MATRIX = ROOT / "evaluation/fine_tuning/p49_2h_augmentation_coverage_matrix_v1.json"

LANES = {"supported_answer": 450, "clarification_required": 125, "bounded_answer": 125}
OUTCOME_CODE = {"supported_answer": "O01", "clarification_required": "O02", "bounded_answer": "O03"}
SUBJECTS = {
    "D01": "DB제도", "D02": "DB제도", "D03": "DC제도", "D04": "DC제도",
    "D07": "IRP", "D08": "IRP", "D09": "연금저축", "D11": "ISA 만기자금",
    "D12": "ISA 만기자금", "D13": "퇴직소득", "D14": "DC제도", "D15": "DC제도",
    "D17": "해당 상품", "D18": "해당 상품", "D19": "해당 상품", "D20": "해당 상품",
    "D21": "해당 상품", "D22": "해당 상품", "D24": "퇴직연금 계좌", "D25": "퇴직연금 제도",
    "D26": "연금계좌", "D27": "연금 수령", "D28": "해당 상품 표", "D30": "해당 상품",
}


def subject_for_requirement(domain: str, canonical_requirement: str) -> str:
    """Return the request-local subject from the bound requirement, not domain.

    Some domains intentionally contain several products/accounts.  A
    domain-level label such as ``D14 = DC`` cannot be used when the selected
    evidence is specifically an IRP requirement.
    """
    if canonical_requirement.startswith("DB."):
        return "DB제도"
    if canonical_requirement.startswith("DC."):
        return "DC제도"
    if canonical_requirement.startswith("IRP.") or ".IRP_" in canonical_requirement:
        return "IRP"
    if canonical_requirement.startswith("pension_savings."):
        return "연금저축"
    if canonical_requirement.startswith("ISA."):
        return "ISA 만기자금"
    if canonical_requirement.startswith("product."):
        return "해당 상품"
    if canonical_requirement.startswith("retirement_pension."):
        return "IRP"
    return SUBJECTS[domain]
CLARIFICATION_CONDITIONS = {
    "D07": ["현재 받은 퇴직급여의 형태", "이전하려는 계좌"],
    "D09": ["올해 연금계좌별 납입 계획", "중도 사용 가능성"],
    "D14": ["가입한 제도", "인출하려는 법정 사유"],
    "D24": ["현재 가입 제도", "이전하려는 계좌"],
    "D26": ["연간 납입 계획", "적용받는 소득·공제 조건"],
}
CLARIFICATION_DECISIONS = {
    "D07": ("퇴직급여를 IRP로 이전할 수 있는지와 처리 방법", "퇴직급여 이전을 검토 중인 상황"),
    "D09": ("연금저축과 IRP 중 어떤 납입 방식을 선택할지", "연금계좌 납입 방식을 정하려는 상황"),
    "D14": ("퇴직 전 적립금 인출이 가능한지", "퇴직 전 자금 사용을 검토 중인 상황"),
    "D24": ("현재 퇴직연금을 다른 계좌로 이전할지", "퇴직연금 이전을 검토 중인 상황"),
    "D26": ("현재 납입 계획에서 세액공제를 받을 수 있는지", "연금계좌 세액공제를 검토 중인 상황"),
}
BOUNDED_FIELDS = {
    "D12": ("ISA.transfer.additional_tax_credit", "ISA.tax_credit.future_limit", "향후 ISA 이전 추가 세액공제 한도"),
    "D17": ("product.risk_grade.current", "product.risk_grade.future", "미래의 구체적 위험등급"),
    "D18": ("product.risk_grade.change_possibility", "product.risk_grade.future", "미래의 구체적 위험등급 또는 변경 시점"),
    "D20": ("product.total_fee", "product.total_fee.future", "향후 총보수율"),
    "D30": (None, "product.future_value", "미래 수익률·미래 위험등급 등 제공 자료 밖 값"),
}
BOUNDED_SLOTS = {
    "D12": ("ISA 만기자금", "future", "추가 세액공제 한도", "구체 한도"),
    "D17": ("해당 상품", "future", "위험등급", "구체 등급"),
    "D18": ("해당 상품", "future", "위험등급", "구체 등급 또는 변경 시점"),
    "D20": ("해당 상품", "future", "총보수율", "구체 보수율"),
    "D30": ("해당 상품", "future", "미래 값", "구체 값 또는 시점"),
}
STYLE = {
    "supported_answer": ("formal", "conversational", "beginner", "technical"),
    "clarification_required": ("conversational", "beginner", "situation", "short"),
    "bounded_answer": ("conversational", "confirmation", "plain_language", "formal"),
}
FORMS = {
    "supported_answer": ("direct", "confirmation", "misconception", "condition", "numeric", "keyword"),
    "clarification_required": ("choice_with_missing_conditions", "ambiguous_reference", "situation_with_missing_conditions"),
    "bounded_answer": ("future_value", "future_date", "prediction", "unsupported_exact_value"),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def largest_remainder(weights: dict[str, int], total: int) -> dict[str, int]:
    base = sum(weights.values())
    raw = {key: value * total / base for key, value in weights.items()}
    result = {key: int(value) for key, value in raw.items()}
    for key in sorted(raw, key=lambda item: (raw[item] - result[item], item), reverse=True)[: total - sum(result.values())]:
        result[key] += 1
    return result


def weighted_domains(pool: list[dict], matrix: dict, lane: str, total: int) -> list[dict]:
    allowed = [row for row in pool if lane in row["allowed_outcomes"]]
    if lane == "clarification_required":
        allowed = [row for row in allowed if row["domain"] in CLARIFICATION_CONDITIONS]
    elif lane == "bounded_answer":
        allowed = [row for row in allowed if row["domain"] in BOUNDED_FIELDS]
    else:
        allowed = [row for row in allowed if row["domain"] != "D30" and row["evidence_role"] == "direct_requirement_evidence"]
    weights = {item["code"]: item["target"] for item in matrix["domain_targets"] if any(row["domain"] == item["code"] for row in allowed)}
    quotas = largest_remainder(weights, total)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in allowed:
        by_domain[row["domain"]].append(row)
    result: list[dict] = []
    offsets = Counter()
    remaining = dict(quotas)
    # Deterministic weighted round-robin: preserve per-domain quotas while
    # avoiding long runs of one evidence/subject contract.
    while any(remaining.values()):
        for domain in sorted(remaining):
            if remaining[domain] <= 0:
                continue
            rows = by_domain[domain]
            result.append(rows[offsets[domain] % len(rows)])
            offsets[domain] += 1
            remaining[domain] -= 1
    return result


def lane_question_types(matrix: dict, lane: str, total: int) -> list[str]:
    code = OUTCOME_CODE[lane]
    weights = {item["code"]: item.get("outcomes", {}).get(code, 0) for item in matrix["question_type_targets"] if item.get("outcomes", {}).get(code, 0)}
    quotas = largest_remainder(weights, total)
    # Do not emit Q01...Q20 in contiguous blocks.  With deterministic HCX
    # generation that would repeatedly pair one domain with one identical
    # question form, manufacturing near-duplicates before validation.
    # This is scheduling only: each frozen quota remains unchanged.
    result: list[str] = []
    remaining = dict(quotas)
    while any(remaining.values()):
        for question_type in sorted(remaining, key=lambda item: (-remaining[item], item)):
            if remaining[question_type] > 0:
                result.append(question_type)
                remaining[question_type] -= 1
    if Counter(result) != Counter(quotas) or len(result) != total:
        raise AssertionError("question-type quota scheduling mismatch")
    return result


def requirement(row: dict, *, supported: bool) -> dict:
    return {
        "canonical_requirement": row["canonical_requirement"], "requirement_kind": "factual",
        "coverage_required": supported, "support_status": "supported" if supported else "unsupported",
        "evidence_chunk_ids": [row["chunk_id"]] if supported else [],
    }


def evidence(row: dict) -> dict:
    return {"chunk_id": row["chunk_id"], "source_id": row["source_id"], "evidence_type": row["evidence_type"], "text": row["evidence_text"]}


def build_request(index: int, lane: str, row: dict, question_type: str, variant: int) -> dict:
    domain = row["domain"]
    subject = subject_for_requirement(domain, row["canonical_requirement"])
    host_contract = {
        "question_scope": row["canonical_requirement"] if lane == "supported_answer" else None,
        "canonical_requirement": row["canonical_requirement"] if lane == "supported_answer" else None,
        "subject": subject,
        "allowed_fields": [row["canonical_requirement"]],
        "forbidden_fields": row["exclusion_constraints"],
        "question_intent_type": FORMS[lane][variant % len(FORMS[lane])],
        "question_register": STYLE[lane][variant % len(STYLE[lane])],
        "question_length_band": ("short", "medium", "long")[variant % 3],
        "diversity_constraints": {
            "semantic_variant_id": f"{lane}:{domain}:{question_type}:{variant:04d}",
            "forbid_previous_question_patterns": True,
            "frozen_seed_paraphrase_forbidden": True,
        },
    }
    base = {
        "full_request_id": f"P49-2H-3F-{index:04d}", "coverage_cell": f"{domain}-{question_type}-{lane}",
        "target_outcome": lane, "contract_lane": lane, "question_type": question_type,
        "factual_domain": domain, "pool_id": row["pool_id"], "source_seed_id": None,
        "generation_status": "not_started", "host_provenance_locked": True,
        "host_question_contract": host_contract, "evidence_chunk_ids": [row["chunk_id"]],
        "source_ids": [row["source_id"]], "allowed_fields": host_contract["allowed_fields"],
        "forbidden_fields": host_contract["forbidden_fields"], "direct_evidence": [evidence(row)],
        "literal_evidence_quotes": row["required_evidence_anchors"], "question_template_id": host_contract["diversity_constraints"]["semantic_variant_id"],
    }
    if lane == "supported_answer":
        return {**base, "requirements": [requirement(row, supported=True)], "supported_requirements": [requirement(row, supported=True)], "unsupported_requirements": [], "missing_conditions": [], "unsupported_target": None}
    if lane == "clarification_required":
        missing = CLARIFICATION_CONDITIONS[domain]
        decision_target, scenario_context = CLARIFICATION_DECISIONS[domain]
        host_contract["question_scope"] = "decision_requires_missing_conditions"
        host_contract["missing_conditions"] = missing
        host_contract["decision_target"] = decision_target
        host_contract["scenario_context"] = scenario_context
        host_contract["required_question_slots"] = ["decision_target", "dependency_on_missing_conditions"]
        return {**base, "requirements": [], "supported_requirements": [], "unsupported_requirements": [], "missing_conditions": missing, "decision_target": decision_target, "scenario_context": scenario_context, "unsupported_target": None, "direct_evidence": [], "evidence_chunk_ids": [], "source_ids": []}
    supported_requirement, unsupported_requirement, target = BOUNDED_FIELDS[domain]
    _, temporal_scope, target_type, concreteness = BOUNDED_SLOTS[domain]
    host_contract["question_scope"] = unsupported_requirement
    host_contract["unsupported_target"] = target
    host_contract["temporal_scope"] = temporal_scope
    host_contract["target_type"] = target_type
    host_contract["concreteness_requirement"] = concreteness
    host_contract["required_question_slots"] = ["subject", "temporal_scope", "target_type", "concreteness_requirement"]
    host_contract["request_local_subject_aliases"] = (["ISA"] if domain == "D12" else ["해당 상품", "이 상품", "위 상품"])
    host_contract["supported_requirements"] = [supported_requirement] if supported_requirement else []
    supported = [requirement(row, supported=True)] if supported_requirement else []
    unsupported = [{"canonical_requirement": unsupported_requirement, "requirement_kind": "factual", "coverage_required": True, "support_status": "unsupported", "evidence_chunk_ids": []}]
    return {**base, "requirements": supported + unsupported, "supported_requirements": supported, "unsupported_requirements": unsupported, "missing_conditions": [], "unsupported_target": target, "direct_evidence": [evidence(row)] if supported else [], "evidence_chunk_ids": [row["chunk_id"]] if supported else [], "source_ids": [row["source_id"]] if supported else []}


def build_manifest(pool: list[dict], matrix: dict) -> list[dict]:
    requests: list[dict] = []
    index = 1
    for lane, total in LANES.items():
        domains = weighted_domains(pool, matrix, lane, total)
        question_types = lane_question_types(matrix, lane, total)
        if len(domains) != total or len(question_types) != total:
            raise AssertionError("semantic schedule quota mismatch")
        for variant, (row, question_type) in enumerate(zip(domains, question_types), start=1):
            requests.append(build_request(index, lane, row, question_type, variant)); index += 1
    return requests


def validate_semantic_manifest(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(rows) != 700 or Counter(row["target_outcome"] for row in rows) != Counter(LANES):
        errors.append("lane_quota_mismatch")
    if len({row["full_request_id"] for row in rows}) != len(rows): errors.append("duplicate_request_id")
    if len({row["question_template_id"] for row in rows}) != len(rows): errors.append("repeated_host_question_template")
    for row in rows:
        lane, host = row["target_outcome"], row["host_question_contract"]
        if not host["subject"] or not host["question_scope"]: errors.append("missing_question_scope")
        if lane == "bounded_answer" and not row["unsupported_target"]: errors.append("bounded_missing_unsupported_target")
        if lane == "clarification_required" and not row["missing_conditions"]: errors.append("clarification_missing_conditions")
        if lane == "supported_answer" and (not row["supported_requirements"] or not row["direct_evidence"]): errors.append("supported_missing_evidence_binding")
    return sorted(set(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=POOL); parser.add_argument("--matrix", type=Path, default=MATRIX)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_requests_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_full_semantic_manifest_v1.json")
    args = parser.parse_args()
    rows = build_manifest(read_jsonl(args.pool), json.loads(args.matrix.read_text(encoding="utf-8")))
    errors = validate_semantic_manifest(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    args.manifest.write_text(json.dumps({"stage": "P49-2H-3F Full Request Manifest Semantics Freeze", "record_count": len(rows), "lane_targets": LANES, "semantic_dry_run": "pass" if not errors else "fail", "errors": errors, "request_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "external_hcx_calls": 0, "accepted_records": 0, "training_export_allowed": False, "tuning_allowed": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(rows), "errors": errors}, ensure_ascii=False))


if __name__ == "__main__": main()
