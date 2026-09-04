"""Build the P49-2H-3A curated original-evidence pool.

The registry is requirement-first.  This script copies exact text and
provenance from chunks.jsonl; it never creates training candidates or calls an
LLM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
MATRIX = ROOT / "evaluation/fine_tuning/p49_2h_augmentation_coverage_matrix_v1.json"


# (domain, canonical requirement, chunk id, required anchors, numeric anchors,
#  field-boundary note).  Every ID is validated against the original corpus.
CURATED_BINDINGS = (
    ("D01", "DB.operation_party", "4607500e74afcdf8-table-6f164502cbce", ("적립금 운용 주체", "DB제도", "회사"), (), "DB 답에 DC 근로자 운용 주체를 섞지 않는다."),
    ("D02", "DB.benefit_determination", "fc71bcf7cc90f68d-table-fc470df2b580", ("퇴직 전 평균임금 30 일분", "계속근로기간"), (), "DB 산식의 평균임금 30일분과 계속근로기간을 모두 보존한다."),
    ("D03", "DC.operation_party", "4607500e74afcdf8-table-6f164502cbce", ("적립금 운용 주체", "DC제도", "근로자"), (), "DC 답에 DB 회사 운용 주체를 섞지 않는다."),
    ("D04", "DC.employer_contribution", "fc71bcf7cc90f68d-table-c1ac92bf85cc", ("연간임금총액", "1/12", "이상"), ("연간임금총액", "1/12"), "법정 사용자 부담금 기준이며 근로자 임의 납입액이 아니다."),
    ("D07", "retirement_income.IRP_transfer.tax_timing", "7878a3be5806fef4-table-a3623398dbaa", ("연금 수령 시까지 과세이연", "세금납부시점", "연금 수령시마다 분산"), (), "세액 자체 계산이나 일반계좌 과세로 확장하지 않는다."),
    ("D08", "retirement_income.IRP_transfer.tax_timing", "7878a3be5806fef4-table-a3623398dbaa", ("연금 수령 시까지 과세이연", "운용 중 세금 없음", "연금 수령시마다 분산"), (), "과세 시점만 답하며 개인별 세액을 추정하지 않는다."),
    ("D09", "pension_savings.tax_credit.limit", "7cce439d30d5a8b0-table-20114875d339", ("연금저축 단독 600만원", "연 900만 원"), ("600만원", "900만 원"), "연금저축 단독 한도와 IRP 합산 한도를 혼동하지 않는다."),
    ("D11", "ISA.transfer.deadline", "ae22159be59440b6-paragraph_group-8d64cc53348b", ("ISA만기자금", "60일 내", "연금계좌"), ("60일",), "ISA 만기 전환 기한이며 미래 제도 변경을 답하지 않는다."),
    ("D12", "ISA.transfer.additional_tax_credit", "ae22159be59440b6-paragraph_group-8d64cc53348b", ("10%", "300만원", "추가 세액공제"), ("10%", "300만원"), "ISA 추가 공제와 일반 연금계좌 한도를 분리한다."),
    ("D13", "retirement_income.IRP_transfer.tax_timing", "7878a3be5806fef4-table-a3623398dbaa", ("퇴직소득세", "과세이연", "연금 수령시마다"), (), "퇴직소득 과세 시점에 한정하며 세율을 임의로 계산하지 않는다."),
    ("D14", "DC.early_withdrawal.allowed_reasons", "15fb5460a23aa10d-paragraph_group-9b55ec13ba82", ("주택 구입", "대통령령", "중도인출"), (), "DC/IRP 가능과 DB 불가를 뒤섞지 않고 이 chunk의 사유 범위 안에서만 답한다."),
    ("D14", "IRP.early_withdrawal.allowed_reasons", "e8d7e6a69504e042-table-e07c4f8c5781", ("중도인출", "주택", "요양"), (), "IRP 사유와 세금 처리를 별도 field로 다룬다."),
    ("D14", "pension_savings.early_withdrawal.allowed_reasons", "a1e78e21d33dafed-table-e9ba0606db15", ("부득이한 사유", "인출"), (), "연금저축 사유를 DC/IRP 법정 사유 목록으로 대체하지 않는다."),
    ("D15", "DC.early_withdrawal.required_documents", "15fb5460a23aa10d-table-7d058f42705f", ("신청양식", "6개월이상 요양", "진단서"), (), "사유별 증빙서류이며 사유 없이 모든 서류를 일반화하지 않는다."),
    ("D17", "product.risk_grade.current", "545de7c663ff2726-paragraph_group-d9754d5d83b6", ("투자 위험 등급", "2등급", "높은위험"), ("2등급",), "현재 위험등급과 과거 변경 이력을 혼동하지 않는다."),
    ("D18", "product.risk_grade.change_possibility", "545de7c663ff2726-paragraph_group-d9754d5d83b6", ("운용실적", "시장", "변경될 수"), (), "변경 가능성만 답하며 미래 특정 등급을 예측하지 않는다."),
    ("D19", "product.risk_grade.historical", "9175b4d6847de4c3-table-012d76a0b2f1", ("변경일", "변경전 위험등급", "변경후 위험등급", "위험등급 변경사유"), ("2016.07.02", "2025.03.28"), "이력 표의 날짜·전후 등급·사유 연결을 보존한다."),
    ("D20", "product.total_fee", "1bfc399c9b3d6a67-table-d384a980cda1", ("지급비율(연간, %)", "총보수･", "총 보수"), (), "기간별 1,000만원 비용 예시를 총보수 답으로 대체하지 않는다."),
    ("D21", "product.period_cost", "545de7c663ff2726-table-c23d15637943", ("1,000만원 투자시", "투자기간별 예시", "1년", "3년", "5년", "10년"), ("1,000만원", "1년", "3년", "5년", "10년"), "기간별 비용 표이며 연간 총보수율을 답으로 대체하지 않는다."),
    ("D22", "product.tracking_index", "8297231e70bc792a-paragraph_group-7ecf4273221c", ("코스닥150 지수", "비교지수", "추종"), (), "추종·비교지수와 수익률 또는 위험등급을 혼동하지 않는다."),
    ("D22", "product.equity_allocation_limit", "8297231e70bc792a-paragraph_group-3455eeb10f78", ("주식 현물 바스켓", "100% 편입"), ("100%",), "해당 상품의 주식 현물 바스켓 편입 가능 범위만 답한다."),
    ("D24", "retirement_pension.in_kind_transfer.IRP.application_route", "afc99f5bd68cc78b-paragraph_group-549eae06e466", ("IRP계좌", "영업점", "모바일", "이전신청"), (), "DB/DC 회사 경로와 IRP 영업점·모바일 경로를 구분한다."),
    ("D25", "retirement_pension.ETF.direct_trade_scope", "570a48e8debe22bd-paragraph_group-e79299cb589a", ("DC/IRP", "직접 매매 가능", "레버리지", "인버스는 금지"), (), "직접 매매 가능 범위와 레버리지·인버스 금지를 함께 유지한다."),
    ("D26", "pension_savings.tax_credit.limit", "7cce439d30d5a8b0-paragraph_group-f2f6ed313014", ("연금저축", "연600만원", "IRP", "연900만원"), ("600만원", "900만원"), "조건·한도와 개인별 실제 환급액을 분리한다."),
    ("D27", "retirement_income.IRP_transfer.tax_timing", "7878a3be5806fef4-table-a3623398dbaa", ("연금수령", "과세이연", "세금납부시점"), (), "수령 방식의 과세 시점이며 개인별 납부 세액은 계산하지 않는다."),
    ("D28", "product.total_fee", "1bfc399c9b3d6a67-table-d384a980cda1", ("지급비율(연간, %)", "종류형 명칭", "총 보수"), (), "표 header와 값의 관계를 보존하고 기간별 비용 표와 섞지 않는다."),
    ("D28", "product.period_cost", "545de7c663ff2726-table-c23d15637943", ("투자기간", "1년", "2년", "3년", "5년", "10년"), ("1년", "2년", "3년", "5년", "10년"), "질문이 요구한 기간 열만 답하고 표 전체를 임의 요약하지 않는다."),
    ("D28", "product.risk_grade.historical", "9175b4d6847de4c3-table-012d76a0b2f1", ("변경일", "변경전 위험등급", "변경후 위험등급", "위험등급 변경사유"), (), "표의 행·열 대응을 보존한다."),
    ("D30", "product.risk_grade.change_possibility", "545de7c663ff2726-paragraph_group-d9754d5d83b6", ("운용실적", "시장", "변경될 수"), (), "bounded-answer optional context only; never bind it as evidence of a future grade."),
)

TABLE_FIELDS = {
    "DB.operation_party": ["적립금 운용 주체", "DB제도"],
    "DB.benefit_determination": ["DB 형 급여 계산", "퇴직 전 평균임금 30 일분", "계속근로기간"],
    "DC.operation_party": ["적립금 운용 주체", "DC제도"],
    "DC.employer_contribution": ["DC 형 급여 계산", "연간임금총액의 1/12 이상"],
    "retirement_income.IRP_transfer.tax_timing": ["퇴직소득세", "운용수익 과세", "세금납부시점"],
    "pension_savings.tax_credit.limit": ["세액공제 납입한도", "연금저축 단독 600만원"],
    "DC.early_withdrawal.required_documents": ["신청양식", "6개월이상 요양", "연간임금총액"],
    "product.risk_grade.historical": ["변경일", "변경전 위험등급", "변경후 위험등급", "위험등급 변경사유"],
    "product.total_fee": ["지급비율(연간, %)", "총보수･", "총 보수"],
    "product.period_cost": ["1,000만원 투자시", "투자기간", "1년", "2년", "3년", "5년", "10년"],
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def optional_calculation_contract(requirement: str) -> dict | None:
    if requirement == "pension_savings.tax_credit.limit":
        return {"operator": "percent_of", "allowed_when": "base and rate anchors are literal in selected evidence", "forbidden": "Do not calculate a personal refund without the required rate and tax context."}
    if requirement == "ISA.transfer.additional_tax_credit":
        return {"operator": "percent_of", "allowed_when": "transfer amount and 10% rate are literal in selected evidence", "forbidden": "Do not exceed the literal 300만원 cap."}
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fine_tuning/p49_2h_curated_evidence_pool_manifest_v1.json")
    args = parser.parse_args()
    corpus = {item["chunk_id"]: item for item in read_jsonl(CORPUS)}
    records = []
    for index, (domain, requirement, chunk_id, anchors, numeric_anchors, constraint) in enumerate(CURATED_BINDINGS, start=1):
        chunk = corpus[chunk_id]
        optional_context = domain == "D30"
        records.append({
            "pool_id": f"P49-2H-POOL-{index:03d}", "domain": domain, "canonical_requirement": requirement,
            "allowed_outcomes": ["bounded_answer"] if optional_context else ["supported_answer", "clarification_required", "bounded_answer"],
            "evidence_role": "optional_context_only" if optional_context else "direct_requirement_evidence",
            "source_id": chunk["source_id"], "chunk_id": chunk_id, "evidence_text": chunk["text"],
            "evidence_type": "table" if chunk["chunk_type"] == "table" else "paragraph",
            "numeric_anchors": list(numeric_anchors), "required_evidence_anchors": list(anchors),
            "table_fields": TABLE_FIELDS.get(requirement, []) if chunk["chunk_type"] == "table" else [],
            "optional_calculation_contract": optional_calculation_contract(requirement),
            "exclusion_constraints": [constraint],
            "notes": "Original-corpus evidence only. This pool row is not a generated candidate and cannot be exported for training.",
        })
    counts = Counter(item["domain"] for item in records)
    target_domains = {item["code"] for item in json.loads(MATRIX.read_text(encoding="utf-8"))["domain_targets"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")
    manifest = {
        "stage": "P49-2H-3A Curated Evidence Pool Build", "pool_schema_version": "p49.2h.curated-evidence-pool.v1",
        "source_corpus": str(CORPUS.relative_to(ROOT)), "record_count": len(records),
        "covered_active_domains": sorted(counts), "coverage_gaps": sorted(target_domains - set(counts)),
        "domain_record_counts": dict(sorted(counts.items())), "source_ids": sorted({item["source_id"] for item in records}),
        "pool_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "candidate_generation_started": False,
        "raw_generation_started": False, "training_export_allowed": False, "tuning_allowed": False,
        "next_required_action": "Run the curated-pool validator, then prepare a 70-100 record pilot only.",
    }
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
