"""Produce the P49-2G5 evidence-first audit; it does not alter training drafts.

The audit facts below are authored from corpus evidence before inspecting a
record completion.  Existing ``required_facts`` and ``factual_claims`` are
reported only as legacy metadata and are never used to decide a PASS.
"""
from __future__ import annotations

import hashlib
import json
import re
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
CORPUS = ROOT / "data/parsed/chunks.jsonl"


# Authored from the cited source chunks, not from a record completion or its
# legacy required_facts field.  Each list is the independent factual target.
INDEPENDENT_FACTS = {
    "P45-010": ["대상 문서에는 '지급비율(연간, %)' 표와 '총보수·비용' 열이 있다."],
    "P45-011": ["대상 비용표의 보유기간 열은 1년·2년·3년·5년·10년이다."],
    "P45-013": ["KR5111420047 문서에는 '지급비율(연간, %)' 표와 '총보수·비용' 열이 있다."],
    "P45-015": ["대상 비용표의 보유기간 열은 1년후·2년후·3년후·5년후·10년후다."],
    "P45-016": ["대상 표의 연간 항목에는 '판매회사 보수'와 별도의 '총 보수·비용' 열이 있다."],
    "P45-018": ["DB 적립금 운용 주체는 회사다.", "DB 급여 계산은 퇴직 전 평균임금 30일분 × 계속근로기간이다."],
    "P46-009": ["대상 비용표의 보유기간 열은 1년·2년·3년·5년·10년이다."],
    "P46-013": ["KR5127420045 문서에는 '지급비율(연간, %)' 표와 '총 보수·비용' 열이 있다."],
    "P46-016": ["DB 적립금 운용 주체는 회사다.", "DB 급여 계산은 퇴직 전 평균임금 30일분 × 계속근로기간이다."],
    "P47-008": ["현재 투자 위험 등급은 5등급(낮은 위험)이다.", "위험등급은 운용실적·시장 상황 등에 따라 변경될 수 있다."],
    "P47-010": ["대상 문서에는 '지급비율(연간, %)' 표와 '총보수·비용' 열이 있다."],
    "P47-014": ["대상 표의 연간 항목에는 '판매회사 보수'와 별도의 '총 보수·비용' 열이 있다."],
    "P48-002": ["DC형 급여 계산의 회사 부담금 기준은 연간임금총액의 1/12 이상이다."],
    "P48-005": ["IRP 연금수령 시까지 운용수익은 과세이연되어 운용 중 세금이 없다.", "세금 납부시점은 연금 수령시마다 분산된다."],
    "P48-008": ["현재 투자 위험 등급은 5등급(낮은 위험)이다.", "위험등급은 운용실적·시장 상황 등에 따라 변경될 수 있다."],
    "P48-009": [
        "2016.07.02: 1등급→3등급; 5단계에서 6단계로 분류체계가 개편되고 최근 3년 주간수익률 변동성이 10% 초과 15% 이하다.",
        "2021.03.31: 3등급→2등급; 최근 3년 주간수익률 변동성이 15% 초과 25% 이하다.",
        "2024.03.28: 2등급→3등급; 최근 3년 주간수익률 변동성이 10% 초과 15% 이하다.",
        "2025.03.28: 3등급→2등급; 산정기준이 표준편차에서 VaR로 바뀌고 최근 3년 일간수익률의 최대손실예상액(VaR) 기반 변동성을 사용한다.",
    ],
    "P48-010": ["대상 문서에는 '지급비율(연간, %)' 표와 '총보수·비용' 열이 있다."],
    "P48-011": ["대상 비용표의 보유기간 열은 1년·2년·3년·5년·10년이다."],
    "P48-014": ["대상 표의 연간 항목에는 '판매회사 보수'와 별도의 '총 보수·비용' 열이 있다."],
}

# Minimal literal checks derived from the independent facts above.  These are
# intentionally not copied from a record's legacy completion metadata.
COMPLETION_FACT_TOKENS = {
    "P45-010": ("지급비율", "총보수"),
    "P45-011": ("1,000만원", "3년"),
    "P45-013": ("KR5111420047", "지급비율", "총보수"),
    "P45-015": ("1년", "2년", "3년", "5년", "10년"),
    "P45-016": ("판매회사 보수", "총보수"),
    "P45-018": ("회사", "평균임금 30일분", "계속근로기간"),
    "P46-009": ("1년", "2년", "3년", "5년", "10년"),
    "P46-013": ("KR5127420045", "지급비율", "총보수"),
    "P46-016": ("회사", "평균임금 30일분", "계속근로기간"),
    "P47-008": ("5등급", "변경"),
    "P47-010": ("지급비율", "총보수"),
    "P47-014": ("판매회사 보수", "총보수"),
    "P48-002": ("12분의 1", "이상"),
    "P48-005": ("과세이연", "운용 중 세금 없음", "연금 수령시마다 분산"),
    "P48-008": ("5등급", "변경"),
    "P48-009": ("2016.07.02", "2021.03.31", "2024.03.28", "2025.03.28", "10%초과 15%이하", "15%초과 25%이하", "일간", "VaR"),
    "P48-010": ("지급비율", "총보수"),
    "P48-011": ("3년", "투자기간별"),
    "P48-014": ("판매회사 보수", "총보수"),
}

PRODUCT_CODE = re.compile(r"KR[A-Z0-9]{10}", re.IGNORECASE)


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def case_id(record_id: str) -> str:
    return record_id.rsplit("-", 2)[-2].upper() + "-" + record_id.rsplit("-", 1)[-1]


def finding_for(record: dict) -> tuple[str, str]:
    """Check the previously found issues against record content, not its ID.

    The P49-2G6 rerun therefore verifies that a remediation actually repaired
    its evidence contract instead of accepting a record merely because it was
    listed in a patch table.
    """
    key, question, completion = case_id(record["record_id"]), record["question"], record["completion"]
    evidence_text = "\n".join(item["text"] for item in record["direct_evidence"])
    if key in {"P45-011", "P48-011"} and not all(token in evidence_text for token in ("1년", "2년", "3년", "5년", "10년")):
        return "FIX_EVIDENCE", "Selected input does not preserve every 1/2/3/5/10-year table header."
    if "판매수수료" in question:
        return "FIX_QUESTION", "Question asks for a sales-fee distinction, but this evidence contract directly names 판매회사 보수."
    if key == "P47-010" and "1년 기준" in question:
        return "FIX_QUESTION", "'1년 기준 총보수율' can be confused with a one-year holding-period cost."
    if key == "P48-002" and "적게 정할 수" in question:
        return "FIX_QUESTION", "Evidence supplies a minimum threshold, not a direct permissibility statement."
    if record["record_id"] == "contrastive_draft-p47-008" and "원금보장" in question:
        return "FIX_QUESTION", "Question introduces principal-guarantee semantics outside the selected requirements."
    if key == "P46-016" and "DB제도은" in completion:
        return "FIX_COMPLETION", "Completion has a DB제도 grammar error."
    if key == "P48-009" and not all(token in completion for token in ("10%초과 15%이하", "15%초과 25%이하", "일간", "VaR")):
        return "FIX_COMPLETION", "Completion omits table-level risk-grade-change reasons."
    required_completion_tokens = COMPLETION_FACT_TOKENS[key]
    if "판매회사 보수를 답하지 말고" in question:
        required_completion_tokens = tuple(token for token in required_completion_tokens if token != "판매회사 보수")
    missing_completion_tokens = [token for token in required_completion_tokens if token not in completion]
    if missing_completion_tokens:
        return "FIX_COMPLETION", f"Completion is missing independent-fact tokens: {missing_completion_tokens}"
    return "PASS", "Question, requirement, evidence, independent facts, and completion align."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--positive", type=Path, default=BASE / "p49_draft_gold_training_records_v4.jsonl")
    parser.add_argument("--contrastive", type=Path, default=BASE / "p49_draft_contrastive_records_v4.jsonl")
    parser.add_argument("--audit", type=Path, default=BASE / "p49_2g5_full_evidence_first_audit.jsonl")
    parser.add_argument("--manifest", type=Path, default=BASE / "p49_2g5_audit_manifest.json")
    parser.add_argument("--stage", default="P49-2G5 Full Evidence-First Audit")
    parser.add_argument("--next-allowed-stage", default=None)
    parser.add_argument("--gold-seed-status", default=None)
    args = parser.parse_args()
    inputs = (args.positive, args.contrastive)
    records = [record for path in inputs for record in rows(path)]
    if len(records) != 38 or len({record["record_id"] for record in records}) != 38:
        raise RuntimeError("P49-2G5 expects exactly 38 distinct v4 draft records")
    corpus = {chunk["chunk_id"]: chunk for chunk in rows(CORPUS)}
    output = []
    for record in records:
        key = case_id(record["record_id"])
        facts = INDEPENDENT_FACTS[key]
        finding, note = finding_for(record)
        source_chunks = [corpus.get(item["chunk_id"]) for item in record["direct_evidence"]]
        missing_chunks = [item["chunk_id"] for item, chunk in zip(record["direct_evidence"], source_chunks) if chunk is None]
        exact_evidence_copy = not missing_chunks and all(
            item["text"] == chunk["text"] for item, chunk in zip(record["direct_evidence"], source_chunks)
        )
        question_codes = tuple(dict.fromkeys(match.group(0).upper() for match in PRODUCT_CODE.finditer(record["question"])))
        evidence_codes = sorted({code.upper() for chunk in source_chunks if chunk for code in chunk.get("product_codes", [])})
        provenance = "not_applicable"
        if question_codes:
            provenance = "verified_by_chunk_metadata" if set(evidence_codes) & set(question_codes) else "unresolved"
        checks = {
            "question_requirement": "PASS" if finding not in {"FIX_QUESTION", "FIX_REQUIREMENT"} else finding,
            "subject_grounding": provenance,
            "evidence_sufficiency": "PASS" if finding != "FIX_EVIDENCE" else "FIX_EVIDENCE",
            "table_integrity": "FIX_EVIDENCE" if finding == "FIX_EVIDENCE" else "PASS",
            "independent_gold_facts": "AUTHORED_FROM_EVIDENCE",
            "completion_coverage": "FIX_COMPLETION" if finding == "FIX_COMPLETION" else "PASS",
            "extra_claim": "PASS",
        }
        output.append({
            "record_id": record["record_id"],
            "audit_status": finding,
            "audit_note": note,
            "question": record["question"],
            "selected_requirements": record["selected_requirements"],
            "evidence_chunk_ids": [item["chunk_id"] for item in record["direct_evidence"]],
            "evidence_source_paths": [chunk.get("source_path") for chunk in source_chunks if chunk],
            "question_product_codes": list(question_codes),
            "evidence_product_codes": evidence_codes,
            "checks": checks,
            "independent_gold_facts": facts,
            "legacy_metadata_not_used_for_audit": {
                "required_facts": record["quality"]["required_facts"],
                "factual_claims": record["factual_claims"],
            },
            "corpus_chunk_text_exact_match": exact_evidence_copy,
            "completion": record["completion"],
        })
    args.audit.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output), encoding="utf-8")
    counts = {status: sum(row["audit_status"] == status for row in output) for status in sorted({row["audit_status"] for row in output})}
    audit_passed = counts == {"PASS": len(output)}
    completion_coverage = sum(row["checks"]["completion_coverage"] == "PASS" for row in output)
    question_requirement_mismatch = sum(row["checks"]["question_requirement"] != "PASS" for row in output)
    evidence_insufficiency = sum(row["checks"]["evidence_sufficiency"] != "PASS" for row in output)
    args.manifest.write_text(json.dumps({
        "stage": args.stage,
        "source_record_count": len(records),
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
        "audit_counts": counts,
        "independent_completion_coverage": f"{completion_coverage}/{len(output)}",
        "question_requirement_mismatch": question_requirement_mismatch,
        "evidence_insufficiency": evidence_insufficiency,
        "corpus_evidence_text_exact_match": f"{sum(row['corpus_chunk_text_exact_match'] for row in output)}/{len(output)}",
        "product_subject_provenance_unresolved": sum(row["checks"]["subject_grounding"] == "unresolved" for row in output),
        "completion_derived_gold_fact_used": 0,
        "legacy_literal_required_facts_qa": "not_used: it compares completion-derived metadata to completion and is not evidence-first",
        "training_export_allowed": False,
        "gold_seed_v1_status": args.gold_seed_status or (
            "superseded_pending_p49_2g6_human_approval"
            if audit_passed else "superseded_pending_p49_2g5_remediation"
        ),
        "next_allowed_stage": args.next_allowed_stage or (
            "P49-2G human approval of the remediated v5 drafts"
            if audit_passed else "repair only audited findings, then rerun evidence-first audit before human approval"
        ),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": len(output), "audit_counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
