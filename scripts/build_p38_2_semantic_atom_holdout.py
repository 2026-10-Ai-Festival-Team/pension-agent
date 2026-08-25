"""Freeze the P38-2 unseen semantic-atom holdout before parser evaluation.

This is a parser-only holdout.  It is never imported by candidate routing,
retrieval, generation, or policy code.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout_metadata.json"


# These questions are a manually specified, frozen P38-2 holdout.  They use
# the existing P38 semantic ontology but deliberately avoid copying the P36/P37
# surface forms used to develop the v1 parser.
SPECS = (
    {
        "question_id": "P38-2-001",
        "question": "확정급여형과 확정기여형에서는 적립 자산을 실제로 누가 굴리며, 퇴직급여 액수는 각각 어떤 방식으로 정해집니까?",
        "subjects": ["account:DB", "account:DC"],
        "actions": ["manage", "compare"],
        "fields": ["operation_party", "benefit_determination"],
        "modifiers": ["account_specific", "comparison"],
    },
    {
        "question_id": "P38-2-002",
        "question": "직장에 다니는 동안 DC 적립금 일부를 쓰려면 인정되는 이유와 입증 문서를 무엇을 준비해야 하나요?",
        "subjects": ["account:DC"],
        "actions": ["withdraw"],
        "fields": ["withdrawal_reason", "required_document"],
        "modifiers": ["before_retirement"],
    },
    {
        "question_id": "P38-2-003",
        "question": "가입자 안내 교육은 매년 최소 몇 차례 해야 하고, 외부 전문기관에게 맡겨도 되나요?",
        "subjects": ["system:retirement_pension"],
        "actions": ["educate"],
        "fields": ["education_frequency", "education_outsourcing"],
        "modifiers": [],
    },
    {
        "question_id": "P38-2-004",
        "question": "연금저축에 혼자 불입한 경우와 IRP까지 합쳐 불입한 경우, 돌려받는 세금 공제의 상한은 어떻게 다릅니까?",
        "subjects": ["account:pension_savings", "account:IRP"],
        "actions": ["contribute", "compare"],
        "fields": ["tax_credit_limit"],
        "modifiers": ["account_specific", "combined_limit", "comparison"],
    },
    {
        "question_id": "P38-2-005",
        "question": "보통 투자통장에서 난 이익은 언제 세금을 매기고, 노후계좌 안의 운용 이익은 언제 과세되는 건가요? 세금이 사라지는 것은 아닌지도 알려주세요.",
        "subjects": ["account:general", "account:pension"],
        "actions": ["receive", "compare"],
        "fields": ["tax_timing"],
        "modifiers": ["account_specific", "comparison", "not_tax_exempt"],
    },
    {
        "question_id": "P38-2-006",
        "question": "국내 거래소의 해외 ETF를 일반 통장에 둘 때와 연금계좌에 담을 때 매매 이익·분배금의 세금 부과 시점이 어떻게 달라지나요?",
        "subjects": ["product:foreign_etf", "account:general", "account:pension"],
        "actions": ["invest", "compare"],
        "fields": ["tax_timing"],
        "modifiers": ["account_specific", "comparison"],
    },
    {
        "question_id": "P38-2-007",
        "question": "55세가 되기 전 연금저축과 IRP에서 자금을 꺼낼 수 있는 근거와 세금 처리는 서로 같은가요?",
        "subjects": ["account:pension_savings", "account:IRP"],
        "actions": ["withdraw", "compare"],
        "fields": ["withdrawal_reason", "tax_treatment"],
        "modifiers": ["before_retirement", "account_specific", "comparison"],
    },
    {
        "question_id": "P38-2-008",
        "question": "ISA 만료 자금을 연금계좌로 옮겨 넣으려면 며칠 안에 처리해야 하고, 추가 공제액은 어떤 한도까지 계산되나요?",
        "subjects": ["account:ISA", "account:pension"],
        "actions": ["transfer"],
        "fields": ["transfer_deadline", "tax_credit_limit"],
        "modifiers": ["maturity_event", "additional_credit", "account_specific"],
    },
    {
        "question_id": "P38-2-009",
        "question": "들고 있는 펀드를 팔지 않은 상태에서 퇴직연금 금융사를 갈아타면, DB·DC 재직자와 IRP 가입자는 어디로 접수해야 하나요?",
        "subjects": ["account:DB", "account:DC", "account:IRP"],
        "actions": ["transfer", "compare"],
        "fields": ["transfer_definition", "application_route"],
        "modifiers": ["in_kind", "account_specific", "comparison"],
    },
    {
        "question_id": "P38-2-010",
        "question": "퇴직연금에서 ETF를 직접 사고팔 수 있다면 가격이 두 배로 움직이거나 반대 방향을 따르는 ETF도 매수할 수 있나요?",
        "subjects": ["system:retirement_pension"],
        "actions": ["invest"],
        "fields": ["etf_direct_trade", "leverage_inverse_restriction"],
        "modifiers": [],
    },
    {
        "question_id": "P38-2-011",
        "question": "KR510902773M의 위험 단계는 현재 몇 등급이고, 시장 여건이 변하면 그 표시도 앞으로 달라질 수 있나요?",
        "subjects": ["product:KR510902773M"],
        "actions": ["invest"],
        "fields": ["risk_grade", "risk_grade_changeability"],
        "modifiers": ["current", "change_possibility"],
    },
    {
        "question_id": "P38-2-012",
        "question": "KR5127450215는 어떤 기준지수의 움직임을 따르며, 주식성 자산은 최대 어느 비중까지 담을 수 있나요?",
        "subjects": ["product:KR5127450215"],
        "actions": ["invest"],
        "fields": ["tracking_index", "equity_allocation_limit"],
        "modifiers": [],
    },
    {
        "question_id": "P38-2-013",
        "question": "KR510902773M C-e에서 해마다 적용되는 보수율과 3년 동안 보유했을 때 금액으로 보이는 비용은 어떤 점이 다른가요?",
        "subjects": ["product:KR510902773M"],
        "actions": ["invest"],
        "fields": ["total_fee", "cost_example"],
        "modifiers": ["annual_rate", "holding_period", "field_boundary"],
    },
    {
        "question_id": "P38-2-014",
        "question": "KR5114420022와 KR5114450222의 위험 분류를 나란히 보면, 더 안정적으로 표시된 것은 어느 쪽인가요?",
        "subjects": ["product:KR5114420022", "product:KR5114450222"],
        "actions": ["compare"],
        "fields": ["risk_grade"],
        "modifiers": ["comparison", "relative_low_risk"],
    },
    {
        "question_id": "P38-2-015",
        "question": "KR5120420039와 KR5120420091의 최신 위험 단계와 예전에 적힌 등급을 구별해서 각각 알려주세요.",
        "subjects": ["product:KR5120420039", "product:KR5120420091"],
        "actions": ["compare"],
        "fields": ["risk_grade"],
        "modifiers": ["comparison", "current", "historical"],
    },
    {
        "question_id": "P38-2-016",
        "question": "DB와 DC 중 회사가 적립해야 하는 금액 기준이 적용되는 제도는 무엇이고, 그 제도에서 운용 결정은 누가 하나요?",
        "subjects": ["account:DB", "account:DC"],
        "actions": ["manage", "compare"],
        "fields": ["contribution_structure", "operation_party"],
        "modifiers": ["account_specific", "comparison"],
    },
    {
        "question_id": "P38-2-017",
        "question": "퇴직급여를 IRP로 넘기면 지금 세금을 내는 대신 나중에 연금으로 받을 때 내는 구조인지, 과세 시점을 설명해 주세요.",
        "subjects": ["account:IRP"],
        "actions": ["transfer"],
        "fields": ["tax_timing"],
        "modifiers": [],
    },
    {
        "question_id": "P38-2-018",
        "question": "연금계좌에서 중도에 해지하지 않고 필요한 금액만 빼는 것과 계좌를 완전히 끝내는 것은 어떻게 다른가요?",
        "subjects": ["account:pension"],
        "actions": ["withdraw", "compare"],
        "fields": ["withdrawal_reason", "tax_treatment"],
        "modifiers": ["comparison"],
    },
)


def _normalise(question: str) -> str:
    text = unicodedata.normalize("NFKC", question).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def _previous_questions() -> list[str]:
    paths = [
        ROOT / "question_bank/development/semantic_atoms_v1.jsonl",
        ROOT / "evaluation/question_bank_v1.jsonl",
        ROOT / "evaluation/question_bank_behavior_contract_v1.jsonl",
        ROOT / "evaluation/closed_core_benchmark_v1.jsonl",
        ROOT / "evaluation/retrieval_questions.jsonl",
        ROOT / "evaluation/p32_holdout_manifest.json",
        ROOT / "evaluation/p33_holdout_manifest.json",
        *(ROOT / f"evaluation/p{phase}_closed_holdout_manifest.json" for phase in range(34, 38)),
    ]
    questions = []
    for path in paths:
        if path.suffix == ".jsonl":
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            raw = json.loads(path.read_text(encoding="utf-8"))
            rows = raw.get("questions", raw.get("rows", [])) if isinstance(raw, dict) else raw
        questions.extend(row["question"] for row in rows if isinstance(row, dict) and isinstance(row.get("question"), str))
    return questions


def _compose(spec: dict) -> list[str]:
    subjects = "+".join(sorted(spec["subjects"]))
    actions = "+".join(sorted(spec["actions"]))
    modifiers = "+".join(sorted(spec["modifiers"])) if spec["modifiers"] else "none"
    return [f"{subjects}.{actions}.{field}[{modifiers}]" for field in sorted(spec["fields"])]


def build() -> tuple[list[dict], dict]:
    ids = [spec["question_id"] for spec in SPECS]
    if len(ids) != len(set(ids)):
        raise SystemExit("P38-2 duplicate question IDs")
    normalized = [_normalise(spec["question"]) for spec in SPECS]
    if len(normalized) != len(set(normalized)):
        raise SystemExit("P38-2 duplicate normalised questions")
    seen = {_normalise(question) for question in _previous_questions()}
    overlap = [spec["question_id"] for spec, question in zip(SPECS, normalized) if question in seen]
    if overlap:
        raise SystemExit(f"P38-2 overlaps prior development material: {overlap}")
    rows = [
        {
            "id": f"ATOM-{spec['question_id']}",
            "source_question_id": spec["question_id"],
            "split": "fresh_holdout_frozen",
            "question": spec["question"],
            "subjects": spec["subjects"],
            "actions": spec["actions"],
            "fields": spec["fields"],
            "modifiers": spec["modifiers"],
            "composed_requirements": _compose(spec),
            "annotation_status": "manual_gold_frozen_v1",
        }
        for spec in SPECS
    ]
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    metadata = {
        "version": "1.0",
        "name": "P38-2 Fresh Semantic-Atom Mini Holdout",
        "status": "frozen_before_isolated_parser_execution",
        "question_count": len(rows),
        "scope": "closed factual semantic decomposition only",
        "excluded": ["candidate_agent", "retrieval", "HCX", "citation", "policy"],
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "normalised_overlap_with_prior_material": 0,
        "go_criteria": {
            "subject_f1": 0.90,
            "action_f1": 0.90,
            "field_f1": 0.85,
            "modifier_f1": 0.80,
            "requirement_exact": 0.80,
        },
    }
    return rows, metadata


def main() -> None:
    rows, metadata = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        display_output = str(OUTPUT.relative_to(ROOT))
    except ValueError:
        display_output = str(OUTPUT)
    print(json.dumps({"questions": len(rows), "manifest_sha256": metadata["manifest_sha256"], "output": display_output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
