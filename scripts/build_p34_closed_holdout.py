"""Freeze the P34 Closed factual generalisation holdout before execution.

P34 is intentionally separate from the development-only P15/P31/P32/P33 and
Closed Core sets.  It contains factual, document-answerable questions only:
no recommendation, personal suitability, clarification, abstention, or prompt
injection cases.  The script validates exact normalised-question non-overlap
against the prior evaluation artifacts, verifies every declared gold chunk
exists in the corpus, and writes a content hash used by later pre-HCX and HCX
runs.

Once the generated manifest has been executed, do not rerun this builder with
modified specs.  Treat it as frozen evidence for P34 and create a new P35
holdout for any post-result work.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation/p34_closed_holdout_manifest.json"


def _normalise_question(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).casefold()


# Each record captures requirements and source evidence before any P34 result
# exists.  The questions deliberately use different surface forms and factual
# combinations from earlier development artifacts; the automatic guard below
# prevents only exact normalised duplicates, while ``freshness_note`` explains
# the semantic distinction reviewers should preserve.
SPECS = (
    {
        "question_id": "P34-001",
        "question": "퇴직 후 받을 금액이 미리 정해지는지와 회사 부담금의 기준만 보면 DB와 DC는 어떻게 구별하나요?",
        "category": "institution_closed",
        "difficulty": "compound",
        "expected_requirement_category": "db_dc_general_comparison",
        "expected_slot_keys": ["db_dc_operation_party", "db_dc_benefit_determination", "db_dc_contribution_structure"],
        "required_requirements": ["DB·DC 급여 결정 방식", "DB·DC 운용 주체", "DC 회사 부담금 기준"],
        "gold_answer_points": ["DB는 급여 수준이 사전에 정해지는 구조", "DC는 회사가 부담금을 정하고 가입자가 운용", "DC 회사 부담금은 연간 임금총액의 12분의 1 이상"],
        "evidence_groups": [["4607500e74afcdf8-paragraph_group-fd0d4e7d80e6", "fc71bcf7cc90f68d-paragraph_group-4d522b97d9ef"]],
        "must_not_include": ["DB와 DC의 운용 주체를 동일하다고 설명"],
        "freshness_note": "기존 DB/DC 비교의 급여·운용축에 DC 부담금 산정 축을 결합한 새 질문이다.",
    },
    {
        "question_id": "P34-002",
        "question": "퇴직연금 가입자 교육은 회사가 직접 해야 하나요? 최소 횟수와 외부에 맡길 수 있는지도 알려주세요.",
        "category": "institution_closed",
        "difficulty": "compound",
        "expected_requirement_category": "participant_education",
        "expected_slot_keys": ["education_provider", "education_frequency", "education_outsourcing"],
        "required_requirements": ["교육 실시 주체", "최소 실시 주기", "위탁 가능 여부"],
        "gold_answer_points": ["사용자가 가입자 교육을 실시", "매년 1회 이상", "퇴직연금사업자 또는 전문기관 위탁 가능"],
        "evidence_groups": [["ae713c70a631594f-paragraph_group-b665fce408b0", "ae713c70a631594f-paragraph_group-fd1124e92346"]],
        "must_not_include": ["교육 주기를 문서 밖 횟수로 단정"],
        "freshness_note": "기존 질문의 DB/DC 운영 주체 대신 교육의 직접 실시·위탁 여부를 묻는다.",
    },
    {
        "question_id": "P34-003",
        "question": "퇴직연금 계좌에서는 ETF를 직접 사고팔 수 있어도 레버리지나 인버스 상품까지 허용되는 건가요?",
        "category": "institution_closed",
        "difficulty": "compound",
        "expected_requirement_category": "retirement_etf_restriction",
        "expected_slot_keys": ["retirement_etf_direct_trade", "retirement_etf_leverage_inverse_restriction"],
        "required_requirements": ["퇴직연금 ETF 직접매매 범위", "레버리지·인버스 제한"],
        "gold_answer_points": ["DC·IRP에서 허용된 ETF는 직접 매매 가능", "레버리지·인버스 ETF는 금지 유지"],
        "evidence_groups": [["570a48e8debe22bd-paragraph_group-e79299cb589a"]],
        "must_not_include": ["레버리지·인버스 ETF가 제한 없이 가능하다고 안내"],
        "freshness_note": "ETF 거래 가능 여부와 레버리지·인버스 제한을 하나의 전제 교정 질문으로 결합했다.",
    },
    {
        "question_id": "P34-004",
        "question": "연금저축만 활용할 때와 IRP를 함께 활용할 때, 공제 대상 납입한도를 각각 따로 봐야 하는 이유와 금액을 알려주세요.",
        "category": "tax_closed",
        "difficulty": "compound",
        "expected_requirement_category": "pension_savings_irp_tax_limit_comparison",
        "expected_slot_keys": ["pension_savings_only_deduction_limit", "pension_savings_irp_combined_deduction_limit"],
        "required_requirements": ["연금저축 단독 세액공제 대상 한도", "IRP 포함 합산 세액공제 대상 한도"],
        "gold_answer_points": ["연금저축 단독 한도와 IRP를 포함한 합산 한도는 구분", "문서상 한도 수치를 각각 제시"],
        "evidence_groups": [["7cce439d30d5a8b0-paragraph_group-f2f6ed313014", "7cce439d30d5a8b0-table-20114875d339"]],
        "must_not_include": ["연간 납입한도 전체를 세액공제 한도와 동일시", "개인별 최종 세액 단정"],
        "freshness_note": "단순 금액 비교 대신 공제 대상 납입한도의 scope 차이를 명시했다.",
    },
    {
        "question_id": "P34-005",
        "question": "연금계좌의 과세이연은 세금을 없애는 뜻인가요, 아니면 과세 시점이 달라지는 건가요? 일반계좌와 대비해 설명해 주세요.",
        "category": "tax_closed",
        "difficulty": "compound",
        "expected_requirement_category": "pension_account_tax_deferral_comparison",
        "expected_slot_keys": ["general_account_tax_timing", "pension_account_tax_deferral"],
        "required_requirements": ["일반계좌 과세 시점", "연금계좌 과세이연의 조건·시점"],
        "gold_answer_points": ["과세이연은 면제가 아니라 과세 시점 이연", "연금계좌는 인출·연금수령 단계의 과세를 구분"],
        "evidence_groups": [["de4f8448134189df-paragraph_group-2a4335a2587e", "de4f8448134189df-paragraph_group-4394f7247e77"]],
        "must_not_include": ["과세이연을 영구 비과세로 표현", "개인별 세율 확정"],
        "freshness_note": "절세 효과가 아니라 과세의 시점과 면제 여부를 구분하도록 설계했다.",
    },
    {
        "question_id": "P34-006",
        "question": "국내 상장 해외 ETF의 매매차익과 분배금은 일반계좌와 연금계좌에서 언제 과세되는지 나눠서 설명해 주세요.",
        "category": "tax_closed",
        "difficulty": "compound",
        "expected_requirement_category": "foreign_etf_account_tax_comparison",
        "expected_slot_keys": ["foreign_etf_general_account_tax", "foreign_etf_pension_account_tax", "foreign_etf_tax_condition"],
        "required_requirements": ["일반계좌 매매차익·분배금 과세", "연금계좌 과세 시점", "문서의 조건·유의사항"],
        "gold_answer_points": ["일반계좌와 연금계좌의 과세 시점 구분", "연금계좌의 과세이연을 인출·수령과 연결"],
        "evidence_groups": [["de4f8448134189df-paragraph_group-2a4335a2587e", "de4f8448134189df-paragraph_group-4394f7247e77", "de4f8448134189df-table-ce8fee5b43be"]],
        "must_not_include": ["모든 해외 ETF에 동일한 결과·세율을 단정"],
        "freshness_note": "계좌별 과세시점에 매매차익과 분배금의 두 소득 흐름을 함께 요구한다.",
    },
    {
        "question_id": "P34-007",
        "question": "연금저축은 일부만 빼는 것이 가능한데 IRP도 같은 방식인가요? IRP에서 법으로 정한 인출 사유와 세금 처리까지 구분해 주세요.",
        "category": "procedure_closed",
        "difficulty": "compound",
        "expected_requirement_category": "pension_savings_irp_withdrawal_comparison",
        "expected_slot_keys": ["pension_savings_withdrawal_scope", "irp_withdrawal_legal_grounds_comparison", "account_withdrawal_tax_treatment"],
        "required_requirements": ["연금저축 인출 범위", "IRP 법정 중도인출 사유", "인출 과세 처리"],
        "gold_answer_points": ["연금저축과 IRP의 인출 조건은 동일하지 않음", "IRP에는 법정사유가 필요", "세법상 사유와 과세 처리를 구분"],
        "evidence_groups": [["e8d7e6a69504e042-paragraph_group-35993691d717", "e8d7e6a69504e042-table-e07c4f8c5781", "e8d7e6a69504e042-table-05de077f1213"]],
        "must_not_include": ["IRP와 연금저축 인출 제한이 같다고 설명", "법정사유와 세법상 부득이한 사유를 동일시"],
        "freshness_note": "인출 가능성뿐 아니라 법정사유와 세금의 별도 기준을 한 번에 검증한다.",
    },
    {
        "question_id": "P34-008",
        "question": "DC 적립금을 중간에 꺼내려면 가능한 사유만 있으면 되나요, 아니면 신청·증빙 절차도 따로 확인해야 하나요?",
        "category": "procedure_closed",
        "difficulty": "compound",
        "expected_requirement_category": "withdrawal_condition_and_procedure",
        "expected_slot_keys": ["dc_withdrawal_conditions", "withdrawal_procedure"],
        "required_requirements": ["DC 중도인출 가능 사유", "신청 절차·증빙"],
        "gold_answer_points": ["중도인출 가능 사유를 문서 기준으로 확인", "사유별 증빙·신청 절차가 필요할 수 있음"],
        "evidence_groups": [["04782a392f49293e-paragraph_group-37b3740ca9e9", "04782a392f49293e-paragraph_group-5ab22c46ff7c"]],
        "must_not_include": ["사유만 있으면 증빙 없이 자동 처리된다고 안내"],
        "freshness_note": "법정사유 나열이 아니라 사유와 실행 절차의 두 evidence 축을 요구한다.",
    },
    {
        "question_id": "P34-009",
        "question": "ISA를 만기 처리한 뒤 연금저축 또는 IRP로 옮길 수 있는 마감일과, 그때 추가로 인정되는 공제 계산을 함께 알려주세요.",
        "category": "procedure_closed",
        "difficulty": "compound",
        "expected_requirement_category": "isa_maturity_transfer",
        "expected_slot_keys": ["isa_transfer_deadline", "isa_transfer_additional_tax_credit"],
        "required_requirements": ["ISA 만기자금 이전 기한", "추가 세액공제 계산 기준·한도"],
        "gold_answer_points": ["60일 이내 전환납입", "전환납입액의 10% 추가 공제 대상", "추가 공제 한도 300만원"],
        "evidence_groups": [["ae22159be59440b6-paragraph_group-8d64cc53348b", "ae22159be59440b6-table-433001f3f808"]],
        "must_not_include": ["개인 소득 조건과 무관한 최종 세액 단정"],
        "freshness_note": "이전 가능 여부가 아닌 만기 후 기한과 별도 공제 계산을 묻는다.",
    },
    {
        "question_id": "P34-010",
        "question": "상품을 현금화하지 않은 채 퇴직연금 사업자만 바꾸는 실물이전은 어떤 제도끼리 가능한가요? 재직 중 DB·DC와 IRP 신청 방식도 비교해 주세요.",
        "category": "compound_closed",
        "difficulty": "compound",
        "expected_requirement_category": "in_kind_transfer_application",
        "expected_slot_keys": ["in_kind_transfer_meaning", "db_dc_in_kind_transfer_application", "irp_in_kind_transfer_application"],
        "required_requirements": ["실물이전 정의·적용 범위", "DB·DC 신청 경로", "IRP 신청 경로"],
        "gold_answer_points": ["동일 제도 안에서 매도 없이 금융기관 변경", "DB·DC는 회사 경유", "IRP는 영업점 또는 모바일 신청"],
        "evidence_groups": [["afc99f5bd68cc78b-paragraph_group-549eae06e466"]],
        "must_not_include": ["DB에서 IRP로 실물이전 가능", "모든 보유상품이 이전 가능하다고 단정"],
        "freshness_note": "실물이전의 제도 범위와 두 신청 채널을 함께 요구한다.",
    },
    {
        "question_id": "P34-011",
        "question": "DC 또는 IRP 안에서 ETF를 고를 때, 직접 거래 허용과 레버리지·인버스 제한을 같은 규칙으로 보면 되나요?",
        "category": "compound_closed",
        "difficulty": "compound",
        "expected_requirement_category": "retirement_etf_restriction",
        "expected_slot_keys": ["retirement_etf_direct_trade", "retirement_etf_leverage_inverse_restriction"],
        "required_requirements": ["DC·IRP ETF 직접매매 범위", "레버리지·인버스 ETF 제한"],
        "gold_answer_points": ["직접 거래가 허용되는 ETF 범위와 제한 상품을 구분", "레버리지·인버스 금지 유지"],
        "evidence_groups": [["570a48e8debe22bd-paragraph_group-e79299cb589a"]],
        "must_not_include": ["직접매매 허용을 레버리지·인버스 허용으로 확대 해석"],
        "freshness_note": "동일 주제이나 직접거래 허용과 제한을 혼동하는 전제를 명시적으로 시험한다.",
    },
    {
        "question_id": "P34-012",
        "question": "DB와 DC 중 회사가 적립금을 운용하는 쪽은 어디이고, 근로자가 운용방법을 선택하는 쪽은 어디인가요? 급여 결정 방식도 함께 짚어주세요.",
        "category": "compound_closed",
        "difficulty": "compound",
        "expected_requirement_category": "db_dc_general_comparison",
        "expected_slot_keys": ["db_dc_operation_party", "db_dc_benefit_determination", "db_dc_contribution_structure"],
        "required_requirements": ["DB·DC 운용 주체", "DB·DC 급여 결정 방식", "DC 부담금 구조"],
        "gold_answer_points": ["DB는 회사가 적립금을 운용", "DC는 근로자가 운용방법을 선택", "DB·DC의 급여·부담금 구조를 구분"],
        "evidence_groups": [["4607500e74afcdf8-paragraph_group-fd0d4e7d80e6", "fc71bcf7cc90f68d-paragraph_group-4d522b97d9ef"]],
        "must_not_include": ["DC 적립금을 회사가 운용한다고 설명"],
        "freshness_note": "운용 주체를 질문 전면에 두고 급여·부담금 구조를 결합한 새 표현이다.",
    },
    {
        "question_id": "P34-013",
        "question": "KR510902773M의 현재 위험등급은 무엇이고, 한 번 정해진 등급이라서 앞으로도 변하지 않는다고 봐도 되나요?",
        "category": "product_fact",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR510902773M:risk_grade"],
        "required_requirements": ["KR510902773M 위험등급", "위험등급 변경 가능성"],
        "gold_answer_points": ["3등급(다소 높은 위험)", "운용실적·시장 상황 등에 따라 위험등급이 변경될 수 있음"],
        "evidence_groups": [["cf922cacac95fad9-paragraph_group-4e8c8991d24f"]],
        "must_not_include": ["위험등급이 영구적으로 고정된다고 단정"],
        "freshness_note": "상품 위험등급 값과 등급의 변경 가능성을 함께 검증한다.",
    },
    {
        "question_id": "P34-014",
        "question": "KR5127450215는 어떤 지수를 따라가도록 운용되고, 주식 관련 자산 비중은 어느 정도까지 가능한가요?",
        "category": "product_fact",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR5127450215:investment_strategy", "KR5127450215:investment_target"],
        "required_requirements": ["KR5127450215 투자전략", "KR5127450215 주식 관련 자산 투자비율"],
        "gold_answer_points": ["코스닥150 지수 수익률 추종", "주식 및 주식관련 파생상품 60% 이상"],
        "evidence_groups": [["8297231e70bc792a-paragraph_group-3455eeb10f78", "8297231e70bc792a-table-c3567ecc05be"]],
        "must_not_include": ["지수 추종을 원금 보장으로 표현"],
        "freshness_note": "위험등급 대신 지수 추종 전략과 투자비율이라는 subject-field 결속을 시험한다.",
    },
    {
        "question_id": "P34-015",
        "question": "KR510902773M의 C-e 클래스에서 연간 총보수·비용과 3년 비용 예시는 같은 단위의 수치인가요? 각 숫자가 뜻하는 바를 구분해 주세요.",
        "category": "product_fact",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR510902773M:total_fee", "KR510902773M:example_cost"],
        "required_requirements": ["KR510902773M C-e 총보수·비용", "KR510902773M 기간별 비용 예시", "연간 비율과 기간별 예시의 차이"],
        "gold_answer_points": ["총보수·비용은 연간 비율", "기간별 예시는 투자금·수익률 가정의 비용 예시", "두 수치를 같은 단위로 혼동하지 않음"],
        "evidence_groups": [["cf922cacac95fad9-table-27acbea49e02", "cf922cacac95fad9-paragraph_group-c9052c282f1a", "cf922cacac95fad9-paragraph_group-50171832b91f"]],
        "must_not_include": ["기간별 비용 예시를 연간 총보수율로 표현"],
        "freshness_note": "기존 비용 질문과 다른 상품·클래스·표현으로 annual fee와 기간별 비용의 경계를 시험한다.",
    },
    {
        "question_id": "P34-016",
        "question": "KR510902773M과 KR510902777M을 위험등급만 놓고 보면 어느 쪽이 더 높은 위험으로 표시돼 있나요?",
        "category": "product_fact_comparison",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR510902773M:risk_grade", "KR510902777M:risk_grade"],
        "required_requirements": ["KR510902773M 위험등급", "KR510902777M 위험등급", "위험등급 비교"],
        "gold_answer_points": ["KR510902773M은 3등급", "KR510902777M은 2등급", "2등급이 더 높은 위험으로 표시"],
        "evidence_groups": [["cf922cacac95fad9-paragraph_group-4e8c8991d24f", "c787719b514f51da-paragraph_group-f00a2b356930"]],
        "must_not_include": ["두 상품의 위험등급을 뒤바꿈", "위험등급만으로 적합성 단정"],
        "freshness_note": "기존 상품명 비교가 아닌 코드 기반 비교로 subject resolution과 two-slot completeness를 시험한다.",
    },
    {
        "question_id": "P34-017",
        "question": "KR5114420022와 KR5114450222의 등급 표시는 각각 몇 등급이며, 더 낮은 위험 등급으로 적힌 상품은 어느 쪽인가요?",
        "category": "product_fact_comparison",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR5114420022:risk_grade", "KR5114450222:risk_grade"],
        "required_requirements": ["KR5114420022 위험등급", "KR5114450222 위험등급", "낮은 위험 비교"],
        "gold_answer_points": ["KR5114420022는 5등급", "KR5114450222는 2등급", "5등급이 낮은 위험으로 표시"],
        "evidence_groups": [["f24a347b7c7a170c-paragraph_group-41f23d8eef8c", "545de7c663ff2726-paragraph_group-d9754d5d83b6"]],
        "must_not_include": ["위험등급을 수익 또는 원금보장으로 해석"],
        "freshness_note": "두 코드의 위험등급과 등급 체계상 비교를 동시에 요구한다.",
    },
    {
        "question_id": "P34-018",
        "question": "KR5120420039와 KR5120420091 중 설명서상 더 낮은 위험으로 분류된 것은 무엇인가요? 두 상품의 등급을 함께 제시해 주세요.",
        "category": "product_fact_comparison",
        "difficulty": "compound",
        "expected_requirement_category": "product_fields",
        "expected_slot_keys": ["KR5120420039:risk_grade", "KR5120420091:risk_grade"],
        "required_requirements": ["KR5120420039 위험등급", "KR5120420091 위험등급", "상대적 위험 비교"],
        "gold_answer_points": ["KR5120420039는 5등급", "KR5120420091은 6등급", "6등급이 더 낮은 위험으로 표시"],
        "evidence_groups": [["fc3cd93441450fa8-paragraph_group-a91cddf920fd", "eefb7f7b407d91de-paragraph_group-07cc1c409cef"]],
        "must_not_include": ["6등급을 원금보장으로 단정", "서로 다른 상품의 등급을 교차 인용"],
        "freshness_note": "위험등급의 product-to-value 결속과 비교 결론을 분리해 시험한다.",
    },
)


def _iter_existing_questions(paths: Iterable[Path]) -> Iterable[tuple[str, str]]:
    for path in paths:
        if not path.is_file() or path == MANIFEST_PATH or path.name in {
            "p34_closed_holdout_manifest.json",
            "p34_closed_pre_hcx.json",
        }:
            continue
        if path.suffix == ".jsonl":
            records = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        elif path.suffix == ".json":
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            records = raw.get("questions", raw.get("rows", [])) if isinstance(raw, dict) else raw
            if not isinstance(records, list):
                continue
        else:
            continue
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("question"), str):
                yield str(path.relative_to(ROOT)), record["question"]


def _corpus_chunk_ids() -> set[str]:
    return {
        json.loads(line)["chunk_id"]
        for line in (ROOT / "data/parsed/chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _manifest_without_hash() -> dict:
    return {
        "version": "1.0",
        "status": "frozen_before_pre_hcx_execution",
        "purpose": "P34 fresh holdout: closed factual generalisation only. Manifest is frozen before the candidate path is run.",
        "candidate": "P33-C4 closed pre-HCX certified candidate",
        "scope": {
            "included": ["institution", "tax", "procedure", "compound closed", "product factual", "product factual comparison"],
            "excluded": ["personalised recommendation", "suitability", "clarify", "abstain", "prompt injection", "external real-time information"],
        },
        "denominators": {"total": len(SPECS), "answerable": len(SPECS), "unsupported": 0},
        "pre_hcx_go_criteria": {
            "requirement_plan_coverage": 1.0,
            "evidence_sufficiency": 1.0,
            "source_relevance_exact_or_manual_equivalent": 1.0,
            "wrong_scope": 0,
        },
        "post_hcx_go_criteria": {
            "strict_useful_minimum": 0.75,
            "provider_schema_citation_critical_failures": 0,
        },
        "questions": [
            {
                **spec,
                "answerability": "answerable",
                "expected_policy_behavior": "answer_with_source",
                "required_original_sources": sorted({chunk_id.split("-", 1)[0] for group in spec["evidence_groups"] for chunk_id in group}),
                "acceptable_equivalent_evidence": sorted({chunk_id for group in spec["evidence_groups"] for chunk_id in group}),
            }
            for spec in SPECS
        ],
    }


def main() -> None:
    corpus_ids = _corpus_chunk_ids()
    declared_ids = {chunk_id for spec in SPECS for group in spec["evidence_groups"] for chunk_id in group}
    missing = sorted(declared_ids - corpus_ids)
    if missing:
        raise SystemExit(f"P34 manifest declares missing corpus chunk IDs: {missing}")

    candidate_questions = {_normalise_question(spec["question"]): spec["question_id"] for spec in SPECS}
    if len(candidate_questions) != len(SPECS):
        raise SystemExit("P34 manifest contains duplicate normalised questions")
    prior_paths = list((ROOT / "evaluation").glob("*.json")) + list((ROOT / "evaluation").glob("*.jsonl"))
    overlaps = [
        {"new_question_id": candidate_questions[_normalise_question(question)], "prior_file": path, "prior_question": question}
        for path, question in _iter_existing_questions(prior_paths)
        if _normalise_question(question) in candidate_questions
    ]
    if overlaps:
        raise SystemExit("P34 has exact normalised question overlap: " + json.dumps(overlaps, ensure_ascii=False))

    manifest = _manifest_without_hash()
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    manifest["validation"] = {
        "exact_normalised_overlap_with_prior_evaluation_files": 0,
        "declared_gold_chunk_ids": len(declared_ids),
        "missing_declared_gold_chunk_ids": 0,
        "group_counts": dict(sorted(Counter(spec["category"] for spec in SPECS).items())),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    display_path = MANIFEST_PATH.relative_to(ROOT) if MANIFEST_PATH.is_relative_to(ROOT) else MANIFEST_PATH
    print(json.dumps({"manifest": str(display_path), "sha256": manifest["manifest_sha256"], **manifest["validation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
