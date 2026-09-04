"""Build a requirement-level provenance audit for the 36 robustness seeds.

This is deliberately an audit artifact, not a training export and not a
rewrite of ``robustness_questions_36.csv``.  It replaces opaque ``CHK-*``
references with corpus chunk IDs only in the generated audit output.  Every
factual requirement is bound to one or more chunks; policy requirements such
as ambiguity clarification are explicitly marked as question-semantic rather
than being falsely presented as corpus facts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
DEFAULT_INPUT = ROOT / "robustness_questions_36.csv"
DEFAULT_AUDIT = ROOT / "evaluation/robustness/p49_2h_robustness_provenance_audit_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "evaluation/robustness/p49_2h_robustness_provenance_manifest_v1.json"


def factual(requirement: str, facts: list[str], *chunk_ids: str) -> dict:
    return {
        "requirement": requirement,
        "requirement_kind": "factual",
        "coverage_required": True,
        "support_status": "supported",
        "evidence_chunk_ids": list(chunk_ids),
        "independent_gold_facts": facts,
    }


def unsupported(requirement: str, fact: str) -> dict:
    return {
        "requirement": requirement,
        "requirement_kind": "factual",
        "coverage_required": True,
        "support_status": "unsupported",
        "evidence_chunk_ids": [],
        "independent_gold_facts": [fact],
    }


def policy(requirement: str, fact: str) -> dict:
    return {
        "requirement": requirement,
        "requirement_kind": "runtime_policy",
        "coverage_required": False,
        "support_status": "question_semantics",
        "evidence_chunk_ids": [],
        "independent_gold_facts": [fact],
    }


def optional(requirement: str, facts: list[str], *chunk_ids: str) -> dict:
    return {
        "requirement": requirement,
        "requirement_kind": "optional_relevant_context",
        "coverage_required": False,
        "support_status": "supported",
        "evidence_chunk_ids": list(chunk_ids),
        "independent_gold_facts": facts,
    }


# These mappings were authored evidence-first from data/parsed/chunks.jsonl.
# A row may have more than one requirement, and a chunk may support more than
# one requirement.  Opaque CHK values from the CSV are intentionally absent.
SPECS: dict[str, list[dict]] = {
    "ROB_001": [factual("retirement_pension.subscriber_education.frequency", ["DB·DC 제도를 운영하는 사용자는 가입자에게 매년 1회 이상 교육해야 한다."], "ae713c70a631594f-paragraph_group-b665fce408b0")],
    "ROB_002": [factual("retirement_pension.system_scope", ["퇴직연금제도는 DB·DC·IRP를 포함한다.", "IRP는 개인형퇴직연금제도다."], "4607500e74afcdf8-paragraph_group-fd0d4e7d80e6")],
    "ROB_003": [factual("DC.delay_interest.start_date", ["정해진 납입기일 또는 연장일 다음 날부터 지연이자가 발생한다."], "46551bfa35d467ed-table-0054e1fe39b8"), factual("DC.delay_interest.rate_bands", ["퇴직 후 14일 또는 합의 연장일까지는 연 10%, 그 다음 날부터 납입일까지는 연 20%다."], "46551bfa35d467ed-table-9466318d50b0")],
    "ROB_004": [factual("retirement_pension.garnishment.protection", ["근로자의 퇴직연금 급여를 받을 권리는 전액 압류 금지 대상이다."], "2ce564b5ddde4f21-paragraph_group-866cbf482ac1")],
    "ROB_005": [factual("pension.actual_receipt_year.definition", ["연금실제수령연차는 실제로 연금을 수령한 연도를 누적한다."], "98556b19ed28c070-paragraph_group-29ad11de5d9a"), factual("pension.actual_receipt_year.tax_reduction", ["이연퇴직소득세 감면은 1~10년차 30%, 11~20년차 40%, 21년차부터 50%다."], "98556b19ed28c070-paragraph_group-ae84e15629c6", "98556b19ed28c070-table-205dd515e51e")],
    "ROB_006": [factual("DB.operation_party", ["DB 적립금은 회사가 운용한다."], "4607500e74afcdf8-table-6f164502cbce"), factual("DC.operation_party", ["DC 적립금은 근로자가 직접 운용한다."], "4607500e74afcdf8-table-6f164502cbce")],
    "ROB_007": [factual("retirement_pension.rule_change.disadvantageous_consent", ["근로자에게 불리한 퇴직연금규약 변경에는 근로자대표 동의가 필요하다."], "93b9b09c57458c3b-paragraph_group-0bdff453a6e2")],
    "ROB_008": [factual("DC.delay_interest.rate_bands", ["퇴직 후 14일 또는 합의 연장일까지는 연 10%, 그 다음 날부터 납입일까지는 연 20%다."], "46551bfa35d467ed-table-9466318d50b0")],
    "ROB_009": [factual("IRP.risky_asset.limit", ["IRP 위험자산 투자 비중은 전체 적립금의 70% 이내다."], "ef05c9c97fbadd27-paragraph_group-c169d907b699")],
    "ROB_010": [factual("retirement_pension.subscriber_education.frequency", ["DB·DC 제도를 운영하는 사용자는 가입자에게 매년 1회 이상 교육해야 한다."], "ae713c70a631594f-paragraph_group-b665fce408b0")],
    "ROB_011": [factual("DC.unpaid_contribution.retirement_deadline", ["회사는 퇴직 시 미납 부담금을 퇴직일부터 14일 이내 납입해야 하며, 특별한 사정이 있으면 당사자 합의로 연장할 수 있다."], "46551bfa35d467ed-paragraph_group-ef7c4c45d935")],
    "ROB_012": [factual("ISA.transfer.deadline", ["ISA 만기자금은 60일 이내 연금계좌로 이전할 수 있다."], "ae22159be59440b6-paragraph_group-8d64cc53348b"), factual("ISA.transfer.additional_tax_credit", ["ISA 만기자금을 연금계좌에 이전하면 이전액의 10%, 최대 300만원이 추가 세액공제 대상이다."], "ae22159be59440b6-paragraph_group-8d64cc53348b")],
    "ROB_013": [factual("executive.retirement_pension.garnishment", ["임원은 근로자퇴직급여 보장법상 압류 보호 대상이 아니며, 퇴직연금은 2분의 1까지 압류 가능하다."], "2ce564b5ddde4f21-paragraph_group-866cbf482ac1")],
    "ROB_014": [factual("pension_savings.tax_credit.eligibility", ["연금저축은 소득이 없어도 가입할 수 있다.", "실질 세액공제는 납부할 세금 등 개인 상황의 영향을 받는다."], "7cce439d30d5a8b0-paragraph_group-f2f6ed313014")],
    "ROB_015": [factual("pension.actual_receipt_year.definition", ["연금실제수령연차는 실제로 연금을 수령한 연도만 누적되며, 인출하지 않은 연도에는 누적되지 않는다."], "98556b19ed28c070-paragraph_group-29ad11de5d9a")],
    "ROB_016": [factual("DB.early_withdrawal.availability", ["DB는 직접 중도인출할 수 없고, 법정사유 충족 시 실무적으로 DC 전환 후 처리할 수 있다."], "4607500e74afcdf8-table-6f164502cbce"), factual("DB.to_DC_for_early_withdrawal.condition", ["회사가 중도인출 목적의 제도 변경을 허용하고 DC 중도인출 사유·시기를 충족해야 한다."], "49ed30e0f7b42e68-paragraph_group-9dd9842bb428")],
    "ROB_017": [factual("sole_proprietor.retirement_pension.eligibility", ["개인사업 대표는 DB·DC 퇴직연금에 가입할 수 없고, 일반 IRP에는 자영업자로 가입할 수 있다."], "61c5315b1e7c0f25-paragraph_group-44168a2ba133")],
    "ROB_018": [factual("ISA.transfer.deadline", ["ISA 만기자금은 60일 이내 연금계좌로 이전해야 추가 세액공제 대상이 된다."], "ae22159be59440b6-paragraph_group-8d64cc53348b"), factual("ISA.transfer.additional_tax_credit", ["이전액의 10%, 최대 300만원이 추가 세액공제 대상이다."], "ae22159be59440b6-paragraph_group-8d64cc53348b")],
    "ROB_019": [policy("recommendation.clarification", "개인 조건 없이 IRP와 연금저축 중 하나를 추천하지 않고 필요한 조건을 질문한다.")],
    "ROB_020": [policy("investment_recommendation.clarification", "위험 감수 수준 등 개인 조건 없이 채권형 또는 주식형을 추천하지 않는다."), optional("investment_considerations", ["투자 선택 시 소득·자산·부채·나이·근속연수 등을 고려한다."], "ae713c70a631594f-paragraph_group-3f366b654f2b")],
    "ROB_021": [policy("retirement_account_recommendation.clarification", "퇴직급여를 받을 계좌 추천에 필요한 개인 조건을 먼저 질문한다."), optional("IRP.transfer.general_rule", ["회사 퇴직연금에서 퇴직 시 받은 일시금은 IRP로 의무 이전하는 구조가 안내돼 있다."], "ef05c9c97fbadd27-paragraph_group-c169d907b699")],
    "ROB_022": [policy("account_reference.ambiguity_clarification", "'그 계좌'의 대상이 확정되지 않았으므로 계좌 종류와 납입 주체를 질문한다.")],
    "ROB_023": [policy("transfer_method.ambiguity_clarification", "'그 방식'이 실물이전인지 현금이전인지 확정되지 않았으므로 방식을 질문한다."), optional("in_kind_transfer.condition", ["실물이전은 동일 제도 간 가능하고 수관 금융기관이 해당 상품을 취급해야 한다."], "afc99f5bd68cc78b-paragraph_group-549eae06e466")],
    "ROB_024": [policy("account_reference.ambiguity_clarification", "연금저축과 IRP가 함께 언급된 상태의 '그 계좌'는 단일 대상으로 해석하지 않고 확인한다.")],
    "ROB_025": [factual("pension_savings.partial_withdrawal", ["연금저축펀드는 부분 인출이 가능하다."], "7cce439d30d5a8b0-paragraph_group-f2f6ed313014"), factual("pension_savings.partial_withdrawal.tax", ["과세재원을 인출하면 16.5% 기타소득세가 적용될 수 있다."], "7cce439d30d5a8b0-paragraph_group-f2f6ed313014")],
    "ROB_026": [factual("in_kind_transfer.excluded_products", ["실물이전 제외상품에는 디폴트옵션상품, 지분증권, 리츠, 사모펀드, ELF, 파생결합증권, RP, MMF, 종금사 발행어음, 금리연동형보험 등이 있다."], "afc99f5bd68cc78b-paragraph_group-549eae06e466")],
    "ROB_027": [factual("DC.subscriber_education.additional_content", ["DC 추가교육에는 사용자 부담금 수준·납입시기·현황, 분산투자 투자원칙, 운용방법별 수익구조·매도기준가·투자위험·수수료가 포함된다."], "ae713c70a631594f-paragraph_group-3f366b654f2b", "ae713c70a631594f-paragraph_group-acf255b8eff3")],
    "ROB_028": [factual("DC.delay_interest.start_date", ["정해진 납입기일 또는 연장일 다음 날부터 지연이자가 발생한다."], "46551bfa35d467ed-table-0054e1fe39b8"), factual("DC.delay_interest.rate_bands", ["퇴직 후 14일 또는 합의 연장일까지는 연 10%, 그 다음 날부터 납입일까지는 연 20%다."], "46551bfa35d467ed-table-9466318d50b0")],
    "ROB_029": [factual("ISA.transfer.deadline", ["ISA 만기자금은 60일 이내 연금계좌로 이전할 수 있다."], "ae22159be59440b6-paragraph_group-8d64cc53348b"), factual("ISA.transfer.additional_tax_credit", ["이전액의 10%, 최대 300만원이 추가 세액공제 대상이다."], "ae22159be59440b6-paragraph_group-8d64cc53348b")],
    "ROB_030": [factual("ISA.transfer.deadline", ["ISA 만기자금은 60일 이내 연금계좌로 이전할 수 있다."], "ae22159be59440b6-paragraph_group-8d64cc53348b"), unsupported("ISA.tax_credit.2027_limit", "2027년 추가 세액공제 한도는 제공된 원본 근거로 확정할 수 없다.")],
    "ROB_031": [factual("retirement_pension.coverage.weekly_hours", ["4주 평균 1주 소정근로시간이 15시간 미만인 근로자는 퇴직급여제도 설정 대상에서 제외된다."], "61c5315b1e7c0f25-paragraph_group-7415ee00da59")],
    "ROB_032": [factual("pension_savings.tax_credit.rate", ["총급여 5,500만원 이하 구간의 세액공제율은 16.5%다."], "7cce439d30d5a8b0-paragraph_group-f2f6ed313014", "7cce439d30d5a8b0-table-20114875d339"), factual("pension_savings.tax_credit.calculation", ["600만원에 16.5%를 적용하면 99만원이다."], "7cce439d30d5a8b0-table-20114875d339")],
    "ROB_033": [factual("DC.delay_interest.rate_bands", ["별도 합의가 없으면 퇴직 후 14일까지는 연 10%, 15일째부터 납입일까지는 연 20%가 적용된다."], "46551bfa35d467ed-table-9466318d50b0")],
    "ROB_034": [unsupported("retirement_pension.subscriber_education.future_change", "내년 가입자교육 의무의 법 개정 여부는 제공된 원본 근거로 확정할 수 없다."), optional("retirement_pension.subscriber_education.current_rule", ["현행 자료상 DB·DC 운영 회사는 매년 1회 이상 가입자교육을 실시해야 한다."], "ae713c70a631594f-paragraph_group-b665fce408b0")],
    "ROB_035": [unsupported("pension_account.tax_credit.2027_combined_limit", "2027년 연금저축·IRP 세액공제 한도는 제공된 원본 근거로 확정할 수 없다."), optional("pension_account.tax_credit.current_limit", ["현행 일반 세액공제 납입한도는 연금저축 단독 600만원, IRP 포함 합산 900만원이다."], "7cce439d30d5a8b0-paragraph_group-f2f6ed313014", "7cce439d30d5a8b0-table-20114875d339"), optional("ISA.transfer.additional_tax_credit", ["ISA 만기자금 이전에 따른 추가 공제한도는 최대 300만원이며, 합산 최대 공제 대상 납입액은 1,200만원이다."], "ae22159be59440b6-paragraph_group-8d64cc53348b", "ae22159be59440b6-table-433001f3f808")],
    "ROB_036": [unsupported("in_kind_transfer.excluded_products.future_status", "다음 분기의 실물이전 제외상품 목록은 제공된 원본 근거로 보장할 수 없다."), optional("in_kind_transfer.current_conditions", ["현행 자료상 실물이전은 동일 제도 간 가능하고 수관 금융기관이 해당 상품을 취급해야 한다."], "afc99f5bd68cc78b-paragraph_group-549eae06e466")],
}


def read_jsonl(path: Path) -> dict[str, dict]:
    return {row["chunk_id"]: row for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def coverage_status(requirements: list[dict], outcome: str) -> str:
    factual = [item for item in requirements if item["requirement_kind"] == "factual" and item["coverage_required"]]
    if not factual:
        return "unresolved" if outcome == "clarification_required" else "none"
    statuses = {item["support_status"] for item in factual}
    if statuses == {"supported"}:
        return "full"
    if statuses == {"unsupported"}:
        return "none"
    return "partial"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    corpus = read_jsonl(CORPUS)
    ids = {record["id"] for record in records}
    if ids != set(SPECS) or len(records) != 36:
        raise RuntimeError("Expected exactly the 36 ROB_001..ROB_036 records and matching specifications.")

    output: list[dict] = []
    for record in records:
        requirements = SPECS[record["id"]]
        real_ids = [chunk_id for item in requirements for chunk_id in item["evidence_chunk_ids"]]
        missing = sorted({chunk_id for chunk_id in real_ids if chunk_id not in corpus})
        computed = coverage_status(requirements, record["outcome"])
        source_chk_ids = json.loads(record["evidence_chunk_ids"])
        output.append({
            "record_id": record["id"],
            "question": record["question"],
            "source_csv_opaque_evidence_ids": source_chk_ids,
            "requirements": requirements,
            "computed_evidence_status": computed,
            "source_csv_evidence_status": record["evidence_status"],
            "evidence_status_consistent": computed == record["evidence_status"],
            "outcome": record["outcome"],
            "open_close": record["open_close"],
            "outcome_is_authoritative": True,
            "actual_chunk_ids_exist": not missing,
            "missing_actual_chunk_ids": missing,
            "audit_status": "REMEDIATION_REQUIRED" if source_chk_ids else "PASS",
            "audit_note": "Audit artifact has real chunk bindings; source CSV remains intentionally unchanged and still contains opaque CHK references.",
        })

    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    all_required = [item for row in output for item in row["requirements"] if item["requirement_kind"] == "factual" and item["coverage_required"]]
    manifest = {
        "stage": "P49-2H Robustness Provenance Audit",
        "source_csv": str(args.input.relative_to(ROOT)),
        "source_csv_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "record_count": len(output),
        "real_chunk_id_resolved": f"{sum(row['actual_chunk_ids_exist'] for row in output)}/{len(output)}",
        "real_chunk_id_missing": sum(len(row["missing_actual_chunk_ids"]) for row in output),
        "requirement_level_factual_count": len(all_required),
        "supported_required_requirements": sum(item["support_status"] == "supported" for item in all_required),
        "unsupported_required_requirements": sum(item["support_status"] == "unsupported" for item in all_required),
        "optional_context_requirements": sum(item["requirement_kind"] == "optional_relevant_context" for row in output for item in row["requirements"]),
        "opaque_chk_references_remaining_in_source_csv": sum(len(row["source_csv_opaque_evidence_ids"]) for row in output),
        "evidence_status_consistent": f"{sum(row['evidence_status_consistent'] for row in output)}/{len(output)}",
        "outcome_authority": "outcome; open_close is a question-form label only",
        "training_export_allowed": False,
        "freeze_allowed": False,
        "next_required_action": "Review audit artifact, then create a remediated seed file with actual requirement-level evidence bindings and rerun this audit.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
