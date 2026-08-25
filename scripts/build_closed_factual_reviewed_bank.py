"""Build a reviewed Closed-factual question-bank view from two source sets.

The source JSONL files stay untouched.  This artifact separates facts that
are necessary to answer the user's question from useful but non-strict
supporting information, so the evaluator does not penalize concise correct
answers for omitting generic warnings or document metadata.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NORMAL = ROOT / "normal_questions.jsonl"
ROBUSTNESS = ROOT / "robustness_questions.jsonl"
OUTPUT = ROOT / "question_bank/development/closed_factual_reviewed_v1.jsonl"
METADATA = ROOT / "question_bank/development/closed_factual_reviewed_v1_metadata.json"


REVIEW = {
    "N-001": {
        "required_facts": [
            "DB 적립금은 회사가 운용한다",
            "DB 퇴직급여는 퇴직 전 평균임금 30일분과 계속근로기간을 기준으로 산정한다",
            "DC는 회사가 연간 임금총액의 1/12 이상을 부담하고 근로자가 운용하며 운용손익이 최종 급여에 반영된다",
        ],
        "optional_supporting_facts": [], "review_status": "reviewed_wording_refined",
    },
    "N-002": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_wording_refined", "terminology_note": "IRP는 '개인형퇴직연금제도'로 표기한다."},
    "N-003": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "N-004": {"required_facts": ["연금저축 단독 세액공제 대상 납입한도는 연 600만원", "연금저축과 IRP 합산 세액공제 대상 납입한도는 연 900만원"], "optional_supporting_facts": ["실제 절세액은 소득 구간별 공제율에 따라 달라진다"], "review_status": "reviewed_rubric_narrowed"},
    "N-006": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "N-008": {"required_facts": ["미래에셋 장기성장포커스 1호는 주식형 펀드", "2025-01-17 기준 위험등급은 1등급(매우 높은 위험)"], "optional_supporting_facts": ["운용사는 미래에셋자산운용", "실적배당형으로 원금손실 가능", "위험등급은 변경될 수 있음"], "review_status": "reviewed_rubric_narrowed"},
    "N-009": {"required_facts": ["장기성장포커스는 1등급(매우 높은 위험)", "프리미엄크레딧알파 채권형은 6등급(매우 낮은 위험)"], "optional_supporting_facts": ["위험등급은 기준일 및 시장·운용실적에 따라 변경될 수 있음", "낮은 위험등급은 원금보장을 뜻하지 않음"], "review_status": "reviewed_rubric_narrowed"},
    "N-010": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "N-013": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "N-014": {"required_facts": ["퇴직급여신청서", "IRP 가입확인서", "퇴직사실 확인 서류"], "optional_supporting_facts": ["일시금 의무이전 예외 시 가입확인서 생략 여부", "건강보험·고용보험 관련 확인 서류 예시"], "review_status": "evidence_pending_additional_source_link", "evidence_note": "핵심 세 서류는 확인됐으나 예외·추가서류는 원본 chunk 연결 전 strict 판정에 사용하지 않는다."},
    "N-017": {"required_facts": ["국공채형은 5등급(낮은 위험)", "주식형은 2등급(높은 위험)"], "optional_supporting_facts": ["두 등급의 기준일", "위험등급은 변경될 수 있음"], "review_status": "reviewed_rubric_narrowed"},
    "N-023": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "N-030": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_accepted"},
    "R-001-TYPO": {"required_facts": ["연금저축 단독 세액공제 대상 납입한도는 연 600만원", "연금저축과 IRP 합산 세액공제 대상 납입한도는 연 900만원"], "optional_supporting_facts": ["실제 절세액은 소득 구간별 공제율에 따라 달라진다"], "review_status": "reviewed_rubric_inherited"},
    "R-002-TYPO": {"required_facts": ["미래에셋 장기성장포커스 1호는 주식형 펀드", "2025-01-17 기준 위험등급은 1등급(매우 높은 위험)"], "optional_supporting_facts": ["운용사는 미래에셋자산운용", "실적배당형으로 원금손실 가능", "위험등급은 변경될 수 있음"], "review_status": "reviewed_rubric_inherited"},
    "R-003-ABBR": {"required_facts": None, "optional_supporting_facts": [], "review_status": "reviewed_rubric_inherited"},
    "R-004-ABBR": {"required_facts": ["연금저축 단독 세액공제 대상 납입한도는 연 600만원", "연금저축과 IRP 합산 세액공제 대상 납입한도는 연 900만원"], "optional_supporting_facts": ["실제 절세액은 소득 구간별 공제율에 따라 달라진다"], "review_status": "reviewed_rubric_inherited"},
    "R-006-COLLOQUIAL": {"required_facts": ["미래에셋 장기성장포커스 1호는 주식형 펀드", "2025-01-17 기준 위험등급은 1등급(매우 높은 위험)"], "optional_supporting_facts": ["운용사는 미래에셋자산운용", "실적배당형으로 원금손실 가능", "위험등급은 변경될 수 있음"], "review_status": "reviewed_rubric_inherited", "answer_style_note": "답변 첫 문장은 '주식형 펀드입니다'처럼 상품 유형을 명시한다."},
}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> tuple[list[dict], dict]:
    source_rows = [("normal_questions", row) for row in _rows(NORMAL)] + [("robustness_questions", row) for row in _rows(ROBUSTNESS)]
    closed = [(dataset, row) for dataset, row in source_rows if row["question_type"] == "closed"]
    ids = [row["question_id"] for _, row in closed]
    if set(ids) != set(REVIEW):
        raise RuntimeError(f"Closed review coverage mismatch: missing={sorted(set(ids)-set(REVIEW))}, stale={sorted(set(REVIEW)-set(ids))}")
    records = []
    for dataset, row in closed:
        review = REVIEW[row["question_id"]]
        required = review["required_facts"] if review["required_facts"] is not None else row["required_facts"]
        optional = review["optional_supporting_facts"]
        records.append({
            "question_id": row["question_id"],
            "source_dataset": dataset,
            "source_path": f"../{dataset}.jsonl",
            "base_question_id": row.get("base_question_id"),
            "question": row["question"],
            "question_type": "closed",
            "category": row["category"],
            "subtype": row["subtype"],
            "expected_behavior": row["expected_behavior"],
            "answerability": row["intents"][0]["answerability"],
            "gold_answer_reference": row["gold_answer"],
            "required_facts": required,
            "optional_supporting_facts": optional,
            "forbidden_claims": row["forbidden_claims"],
            "evidence": row["evidence"],
            "expected_source_files": row["expected_source_files"],
            "review_status": review["review_status"],
            "review_notes": {key: value for key, value in review.items() if key not in {"required_facts", "optional_supporting_facts", "review_status"}},
            "rubric_contract": {"required_facts_are_strict": True, "optional_supporting_facts_are_not_strict": True, "forbidden_claims_are_strict": True},
        })
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    metadata = {
        "name": "Closed Factual Reviewed Rubric v1",
        "scope": "Closed factual only; open/advisory items intentionally excluded.",
        "question_count": len(records),
        "normal_closed_count": sum(dataset == "normal_questions" for dataset, _ in closed),
        "robustness_closed_count": sum(dataset == "robustness_questions" for dataset, _ in closed),
        "source_sha256": {"normal_questions.jsonl": _source_hash(NORMAL), "robustness_questions.jsonl": _source_hash(ROBUSTNESS)},
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        "status_counts": {status: sum(row["review_status"] == status for row in records) for status in sorted({row["review_status"] for row in records})},
        "pending_evidence_confirmation": ["N-014"],
        "fresh_holdout": False,
        "hcx_calls": 0,
        "candidate_agent_changed": False,
    }
    return records, metadata


def main() -> None:
    records, metadata = build()
    OUTPUT.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"question_count": metadata["question_count"], "status_counts": metadata["status_counts"], "pending_evidence_confirmation": metadata["pending_evidence_confirmation"], "hcx_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
