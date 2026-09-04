"""Prepare the 35-record P49-2H-3C contract-split micro-pilot.

This only writes host-owned requests.  It never calls HCX, writes no training
record, and leaves the P49-2H-3B failed pilot untouched for comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POOL = ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_v1.jsonl"
CONTRACT = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_pilot_v1.json"


SUPPORTED_DOMAINS = "D01 D02 D03 D04 D07 D09 D11 D12 D14 D15 D17 D18 D19 D20 D21".split()
CLARIFICATION_SPECS = (
    ("D09", "연금저축과 IRP 중 어느 쪽이 저에게 더 유리한가요?", ["올해 각 계좌에 납입할 금액", "중도 인출 가능성"]),
    ("D14", "퇴직 전에 적립금을 빼도 될까요?", ["가입한 제도", "인출하려는 사유"]),
    ("D20", "이 상품 비용이 괜찮은 편인가요?", ["비교할 상품", "투자 기간"]),
    ("D21", "이 펀드에 투자하면 비용이 얼마나 들까요?", ["투자 금액", "예상 보유 기간"]),
    ("D24", "퇴직연금 이전은 어떻게 하는 게 좋을까요?", ["현재 가입 제도", "이전하려는 계좌"]),
    ("D09", "연금저축만 할지 IRP도 같이 만들지 추천해 주세요.", ["연간 납입 계획", "자금 사용 가능성"]),
    ("D14", "급하게 돈이 필요한데 연금에서 꺼낼 수 있나요?", ["계좌 종류", "법정 사유 해당 여부"]),
    ("D20", "수수료가 낮은 상품을 골라주세요.", ["비교 대상 상품", "투자 기간"]),
    ("D21", "몇 년 넣어두면 비용이 적게 드나요?", ["투자 상품", "투자 금액"]),
    ("D24", "제가 가진 퇴직연금을 다른 곳으로 옮겨도 될까요?", ["현재 제도", "목적 계좌"]),
)
BOUNDED_SPECS = (
    ("D18", "이 상품의 내년 위험등급은 몇 등급이 될까요?", "product.risk_grade.future", "내년의 구체적 위험등급"),
    ("D18", "이 상품 위험등급이 다음 달에 어떻게 바뀔지 알려주세요.", "product.risk_grade.future", "다음 달의 구체적 위험등급"),
    ("D17", "현재 2등급인 이 상품은 내년에 몇 등급이 될까요?", "product.risk_grade.future", "내년의 구체적 위험등급"),
    ("D18", "이 상품의 위험등급은 내년에 오를까요, 내려갈까요?", "product.risk_grade.future", "내년 위험등급 변화 방향"),
    ("D17", "이 상품의 내년 위험등급을 확정해서 말해 주세요.", "product.risk_grade.future", "내년 확정 위험등급"),
    ("D18", "시장 상황이 나쁘면 이 상품 위험등급이 몇 등급이 되나요?", "product.risk_grade.future", "시장 상황별 미래 위험등급"),
    ("D17", "현재 높은위험 등급인 이 상품은 3년 뒤 몇 등급인가요?", "product.risk_grade.future", "3년 뒤 구체적 위험등급"),
    ("D17", "앞으로 이 상품은 고위험 등급으로 바뀌나요?", "product.risk_grade.future", "향후 위험등급 변화 방향"),
    ("D18", "내년 위험등급을 숫자로 예측해 주세요.", "product.risk_grade.future", "내년 위험등급 숫자"),
    ("D18", "앞으로 위험등급이 바뀔 날짜를 미리 알려줄 수 있나요?", "product.risk_grade.future", "향후 위험등급 변경 시점"),
)
QUESTION_TYPES = ("Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "Q11", "Q12", "Q13", "Q14", "Q15", "Q19", "Q20")
SEED_BY_DOMAIN = defaultdict(lambda: "ROB_012", {
    "D01": "ROB_006", "D02": "ROB_006", "D03": "ROB_006", "D04": "ROB_003", "D07": "ROB_012",
    "D09": "ROB_032", "D11": "ROB_012", "D12": "ROB_012", "D14": "ROB_016", "D15": "ROB_016",
    "D17": "ROB_027", "D18": "ROB_027", "D19": "ROB_027", "D20": "ROB_035", "D21": "ROB_035", "D24": "ROB_023",
})
QUESTION_VARIATION_CONTROLS = {
    "Q01": {"register": "formal", "length": "short", "query_form": "direct", "lexical_constraint": "제도 용어를 그대로 사용"},
    "Q02": {"register": "conversational", "length": "short", "query_form": "direct", "lexical_constraint": "일상 표현 사용"},
    "Q03": {"register": "conversational", "length": "short", "query_form": "abbreviation", "lexical_constraint": "허용된 약어만 사용"},
    "Q04": {"register": "conversational", "length": "short", "query_form": "typo_spacing", "lexical_constraint": "의미를 바꾸지 않는 띄어쓰기 변형"},
    "Q05": {"register": "beginner", "length": "medium", "query_form": "plain_language", "lexical_constraint": "전문용어를 설명형 표현으로 치환"},
    "Q06": {"register": "formal", "length": "medium", "query_form": "technical", "lexical_constraint": "정확한 제도 용어 사용"},
    "Q07": {"register": "conversational", "length": "short", "query_form": "misconception", "lexical_constraint": "잘못된 전제를 하나만 포함"},
    "Q08": {"register": "conversational", "length": "medium", "query_form": "confirmation", "lexical_constraint": "확인형 어미 사용"},
    "Q11": {"register": "conversational", "length": "medium", "query_form": "exclusive_scope", "lexical_constraint": "제외 대상을 명시"},
    "Q12": {"register": "formal", "length": "medium", "query_form": "multi_field", "lexical_constraint": "host requirement 범위 밖 field 금지"},
    "Q13": {"register": "beginner", "length": "long", "query_form": "situation", "lexical_constraint": "개인 상황은 근거 밖 사실 없이 일반화"},
    "Q14": {"register": "conversational", "length": "short", "query_form": "keyword", "lexical_constraint": "하나의 field만 지칭"},
    "Q15": {"register": "conversational", "length": "medium", "query_form": "numeric", "lexical_constraint": "근거의 숫자만 사용"},
    "Q19": {"register": "conversational", "length": "medium", "query_form": "correction", "lexical_constraint": "정정 요청을 하나만 포함"},
    "Q20": {"register": "conversational", "length": "long", "query_form": "condition", "lexical_constraint": "조건은 하나만 추가"},
}
ANSWER_CONTRACTS = {
    "DB.operation_party": {"required_terms": ["회사"], "forbidden_terms": ["근로자"], "unsupported_caveat_terms": []},
    "DB.benefit_determination": {"required_terms": ["평균임금", "30일", "계속근로기간"], "forbidden_terms": [], "unsupported_caveat_terms": []},
    "DC.operation_party": {"required_terms": ["근로자"], "forbidden_terms": ["DB제도", "회사가 운용"], "unsupported_caveat_terms": []},
    "DC.employer_contribution": {"required_terms": ["1/12", "이상"], "forbidden_terms": [], "unsupported_caveat_terms": []},
    "retirement_income.IRP_transfer.tax_timing": {"required_terms": ["과세이연", "연금 수령"], "forbidden_terms": ["세율"], "unsupported_caveat_terms": []},
    # A direct-evidence chunk can legitimately contain adjacent fields.  These
    # contracts deliberately define the *answerable* field, not every token in
    # the retrieved chunk.  This prevents the v3 D09 false-negative where an
    # answer about the pension-savings-only limit wandered into the IRP-combined
    # limit and an unsupported income-rate caveat.
    "pension_savings.tax_credit.limit": {"required_terms": ["600만원"], "forbidden_terms": ["900만원", "IRP"], "unsupported_caveat_terms": ["총급여", "종합소득", "세액공제율"]},
    "ISA.transfer.deadline": {"required_terms": ["60일"], "forbidden_terms": ["10%", "300만원", "추가 세액공제"], "unsupported_caveat_terms": ["절세 혜택"]},
    "ISA.transfer.additional_tax_credit": {"required_terms": ["10%", "300만원"], "forbidden_terms": ["60일"], "unsupported_caveat_terms": ["최소 3,000만원"]},
    "DC.early_withdrawal.allowed_reasons": {"required_terms": ["주택 구입"], "forbidden_terms": [], "unsupported_caveat_terms": []},
    "DC.early_withdrawal.required_documents": {"required_terms": ["신청", "진단서"], "forbidden_terms": [], "unsupported_caveat_terms": ["시장 상황"]},
    "product.risk_grade.current": {"required_terms": ["2등급", "높은위험"], "forbidden_terms": ["변경일"], "unsupported_caveat_terms": []},
    "product.risk_grade.change_possibility": {"required_terms": ["운용실적", "시장", "변경될 수"], "forbidden_terms": ["내년"], "unsupported_caveat_terms": []},
    "product.risk_grade.historical": {"required_terms": ["2016", "2025", "분류체계", "VaR"], "forbidden_terms": [], "unsupported_caveat_terms": []},
    "product.total_fee": {"required_terms": ["총보수"], "forbidden_terms": ["1,000만원", "투자기간별"], "unsupported_caveat_terms": []},
    "product.period_cost": {"required_terms": ["1,000만원", "1년", "3년", "5년", "10년"], "forbidden_terms": ["지급비율(연간"], "unsupported_caveat_terms": ["시장 상황"]},
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def host_requirement(row: dict, *, coverage_required: bool, support_status: str, chunk_ids: list[str]) -> dict:
    return {
        "canonical_requirement": row["canonical_requirement"], "requirement_kind": "factual",
        "coverage_required": coverage_required, "support_status": support_status, "evidence_chunk_ids": chunk_ids,
    }


def direct_evidence(row: dict) -> dict:
    return {"chunk_id": row["chunk_id"], "source_id": row["source_id"], "evidence_type": row["evidence_type"], "text": row["evidence_text"]}


def supported_request(index: int, row: dict) -> dict:
    question_type = QUESTION_TYPES[(index - 1) % len(QUESTION_TYPES)]
    return {
        "micro_request_id": f"P49-2H-3C-{index:03d}", "contract_lane": "supported_answer",
        "source_seed_id": SEED_BY_DOMAIN[row["domain"]], "question_type": question_type,
        "factual_domain": row["domain"], "pool_id": row["pool_id"], "generation_status": "not_started",
        "host_provenance_locked": True, "augmentation_type": f"{QUESTION_TYPES[(index - 1) % len(QUESTION_TYPES)]}:single_field",
        "coverage_cell": f"{row['domain']}-{question_type}-supported_answer",
        "variation_control": QUESTION_VARIATION_CONTROLS[question_type],
        "semantic_focus": row["canonical_requirement"],
        "answer_contract": ANSWER_CONTRACTS[row["canonical_requirement"]],
        "requirements": [host_requirement(row, coverage_required=True, support_status="supported", chunk_ids=[row["chunk_id"]])],
        "direct_evidence": [direct_evidence(row)], "literal_evidence_quotes": row["required_evidence_anchors"],
        "field_constraints": row["exclusion_constraints"], "table_fields": row["table_fields"], "numeric_anchors": row["numeric_anchors"],
    }


def clarification_request(index: int, row: dict, spec: tuple[str, str, list[str]]) -> dict:
    _, scenario, missing_conditions = spec
    return {
        "micro_request_id": f"P49-2H-3C-{index:03d}", "contract_lane": "clarification_required",
        "source_seed_id": SEED_BY_DOMAIN[row["domain"]], "question_type": "Q09", "factual_domain": row["domain"],
        "coverage_cell": f"{row['domain']}-Q09-clarification_required",
        "pool_id": row["pool_id"], "generation_status": "not_started", "host_provenance_locked": True,
        "augmentation_type": "Q09:missing_condition", "user_question_scenario": scenario, "missing_conditions": missing_conditions,
        "requirements": [host_requirement(row, coverage_required=False, support_status="supported", chunk_ids=[])],
        "direct_evidence": [], "literal_evidence_quotes": [],
    }


def bounded_request(index: int, row: dict, spec: tuple[str, str, str, str]) -> dict:
    _, scenario, unsupported_requirement, unsupported_target = spec
    return {
        "micro_request_id": f"P49-2H-3C-{index:03d}", "contract_lane": "bounded_answer",
        "source_seed_id": SEED_BY_DOMAIN[row["domain"]], "question_type": "Q17", "factual_domain": row["domain"],
        "coverage_cell": f"{row['domain']}-Q17-bounded_answer",
        "pool_id": row["pool_id"], "generation_status": "not_started", "host_provenance_locked": True,
        "augmentation_type": "Q17:future_fact_limit", "user_question_scenario": scenario,
        "supported_requirements": [host_requirement(row, coverage_required=True, support_status="supported", chunk_ids=[row["chunk_id"]])],
        "unsupported_requirements": [{"canonical_requirement": unsupported_requirement, "requirement_kind": "factual", "coverage_required": True, "support_status": "unsupported", "evidence_chunk_ids": []}],
        "unsupported_target": unsupported_target, "direct_evidence": [direct_evidence(row)],
        "literal_evidence_quotes": row["required_evidence_anchors"], "field_constraints": row["exclusion_constraints"],
        # Table/header anchors prove provenance, but do not all have to appear
        # verbatim in a natural answer.  The requirement-level answer contract
        # is the authority for bounded supported-part coverage.
        "supported_answer_required_terms": ANSWER_CONTRACTS[row["canonical_requirement"]]["required_terms"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=POOL)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_requests_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_manifest_v1.json")
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    pool = read_jsonl(args.pool)
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in pool:
        by_domain[row["domain"]].append(row)
    requests, index = [], 1
    for domain in SUPPORTED_DOMAINS:
        row = next(row for row in by_domain[domain] if row["evidence_role"] == "direct_requirement_evidence")
        requests.append(supported_request(index, row)); index += 1
    for spec in CLARIFICATION_SPECS:
        row = next(row for row in by_domain[spec[0]] if row["evidence_role"] == "direct_requirement_evidence")
        requests.append(clarification_request(index, row, spec)); index += 1
    for spec in BOUNDED_SPECS:
        row = next(row for row in by_domain[spec[0]] if row["evidence_role"] == "direct_requirement_evidence")
        requests.append(bounded_request(index, row, spec)); index += 1
    counts = Counter(row["contract_lane"] for row in requests)
    targets = contract["lane_targets"]
    if dict(counts) != targets or len(requests) != contract["micro_pilot_target"]:
        raise RuntimeError("Micro-pilot plan does not match its frozen lane targets.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in requests), encoding="utf-8")
    manifest = {
        "stage": contract["stage"], "status": "prepared_not_executed", "request_count": len(requests),
        "lane_targets": targets, "lane_actual": dict(counts), "active_domains": sorted({row["factual_domain"] for row in requests}),
        "request_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "hcx_calls": 0,
        "accepted_records": 0, "training_export_allowed": False, "tuning_allowed": False,
        "next_required_action": "Review outcome-specific requests, then explicitly authorize a 35-record HCX micro-pilot.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
