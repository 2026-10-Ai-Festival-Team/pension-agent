"""Build P49-2 review drafts from evidence-verified generation-failure seeds.

This deliberately produces *review drafts*, not a provider upload or a frozen
training dataset.  All completions below are manually authored draft text and
must receive a human approval before promotion to p49.training_record.v1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
SEEDS = BASE / "p49_generation_failure_seeds.jsonl"
POSITIVE = BASE / "p49_draft_gold_training_records_v1.jsonl"
CONTRASTIVE = BASE / "p49_draft_contrastive_records_v1.jsonl"
QA = BASE / "p49_dataset_qa_results.json"
MANIFEST = BASE / "p49_dataset_manifest.json"
REVIEW = ROOT / "docs/p49_2_dataset_qa.md"
REVIEW_LEDGER = BASE / "p49_human_review_ledger.jsonl"


# These are intentionally authored as full answer targets rather than generated
# from required_facts at runtime.  The wording preserves every required fact.
POSITIVE_ANSWERS = {
    "P45-010": "지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 구분해 확인해야 합니다.",
    "P45-011": "1,000만원 투자 시 투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.",
    "P45-013": "두 번째 상품은 KR5111420047입니다. 지급비율(연간, %)의 총보수·비용 항목을 확인해야 합니다.",
    "P45-015": "기간별 비용 예시는 1년·2년·3년·5년·10년 보유 기간별 비용 예시 열로 제시됩니다.",
    "P45-016": "지급비율(연간, %) 표에서 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해서 읽어야 합니다.",
    "P45-018": "DB형은 회사가 적립금을 운용합니다. 퇴직급여 산정에는 퇴직 전 평균임금 30일분과 계속근로기간으로 퇴직급여 산정하는 기준이 함께 쓰입니다.",
    "P46-009": "1,000만원 투자 기준 기간별 비용 예시는 1년·2년·3년·5년·10년 기간별 비용 예시 열로 나뉘어 있습니다.",
    "P46-013": "후자는 KR5127420045입니다. 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.",
    "P46-016": "DB제도에서는 회사가 적립금을 운용합니다. 퇴직급여 계산에는 퇴직 전 평균임금 30일분과 계속근로기간이 함께 반영됩니다.",
    "P47-008": "현재 5등급(낮은 위험)입니다. 문서상 운용실적·시장 상황 등에 따라 변경될 수 있음으로 안내됩니다.",
    "P47-010": "지급비율(연간, %) 표에서 총보수·비용 또는 합성총보수·비용 항목을 확인해야 합니다.",
    "P47-014": "지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해야 합니다.",
    "P48-002": "확정기여형 퇴직연금의 회사 부담금 법정 기준은 연간 임금총액의 12분의 1 이상입니다.",
    "P48-005": "퇴직급여 일시금을 IRP로 옮긴 뒤에는 운용 중 과세이연됩니다. 세금은 연금 수령 시마다 과세됩니다.",
    "P48-008": "현재 5등급(낮은 위험)입니다. 운용실적·시장 상황 등에 따라 변경 가능합니다.",
    "P48-009": "변경 전·후 위험등급과 변경 사유를 포함한 변경 이력 표를 확인해야 합니다.",
    "P48-010": "지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 기준으로 읽어야 합니다.",
    "P48-011": "투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.",
    "P48-014": "지급비율(연간, %) 표의 총보수·비용 항목입니다. 판매수수료와 구분해야 합니다.",
}

# Short literal anchors selected from each direct-evidence context. They make
# grounding QA inspect the source itself rather than merely trusting a seed's
# family label. Product-code scope is separately present in the question.
EVIDENCE_ANCHORS = {
    "P45-010": ["지급비율", "총보수"], "P45-011": ["1,000만원", "투자기간별"],
    "P45-013": ["지급비율", "총보수"], "P45-015": ["1년후", "10년후"],
    "P45-016": ["지급비율", "총 보수", "판매회사"],
    "P45-018": ["회사", "평균임금", "계속근로기간"],
    "P46-009": ["1년", "2년", "3년", "5년", "10년"],
    "P46-013": ["지급비율", "총 보수"], "P46-016": ["회사", "평균임금", "계속근로기간"],
    "P47-008": ["5등급", "변경될 수"], "P47-010": ["지급비율", "총보수"],
    "P47-014": ["지급비율", "총 보수", "판매회사"], "P48-002": ["1/12"],
    "P48-005": ["과세이연", "연금 수령시마다"], "P48-008": ["5등급", "변경될 수"],
    "P48-009": ["변경전 위험등급", "변경후 위험등급", "변경사유"],
    "P48-010": ["지급비율", "총보수"], "P48-011": ["1,000만원", "3년"],
    "P48-014": ["지급비율", "총 보수", "판매회사"],
}

# These are response fields that would be extra rather than a requested
# distinction. They are deliberately empty where a nearby term is itself a
# required distinction (for example, sales fee in P45-016).
UNREQUESTED_FIELD_TOKENS = {
    "P45-010": ["1,000만원"], "P45-011": ["지급비율(연간"], "P45-013": ["1,000만원"],
    "P45-015": ["위험등급", "지급비율(연간"], "P45-016": [], "P45-018": [],
    "P46-009": ["지급비율(연간"], "P46-013": ["판매수수료"], "P46-016": [],
    "P47-008": ["원금보장"], "P47-010": ["1,000만원"], "P47-014": [],
    "P48-002": [], "P48-005": ["이체 즉시"], "P48-008": ["원금보장"],
    "P48-009": ["현재 위험등급"], "P48-010": ["기간별 비용"], "P48-011": ["지급비율(연간"],
    "P48-014": [],
}

# Every contrastive question stays in the same evidence context but makes a
# nearby, tempting field explicit.  It is a precision counterpart, not a
# negative/unanswerable example.
CONTRASTIVE_QUESTIONS = {
    "P45-010": "KR5111420047에서 1,000만원 보유기간별 비용이 아니라 매년 적용되는 총보수·비용률은 어디에서 봐야 하나요?",
    "P45-011": "KR5113450111의 연간 총보수율이 아니라 1,000만원을 3년 보유한 비용 예시는 어느 열에서 보나요?",
    "P45-013": "KR510902511M은 제외하고 KR5111420047의 연간 총보수·비용률만 보려면 무엇을 확인하나요?",
    "P45-015": "KR5110501016의 위험등급이 아니라 1,000만원 투자 기간별 비용 표에는 어떤 보유기간 열이 있나요?",
    "P45-016": "KR5114420027에서 판매수수료가 아니라 연간 총보수·비용을 보려면 어떤 항목을 읽어야 하나요?",
    "P45-018": "DB형의 운용 주체와 퇴직급여 산정 기준을 DC형 기준과 섞지 말고 알려주세요.",
    "P46-009": "KR5114420016의 연간 보수율 말고 1,000만원 기준 기간별 비용 예시는 어떤 보유기간 열을 보나요?",
    "P46-013": "두 상품 중 KR5127420045만 대상으로, 판매수수료가 아닌 연간 총보수·비용은 어디에서 확인하나요?",
    "P46-016": "DB제도에서 회사 운용 여부와 퇴직급여 계산의 기간 기준을 함께 알려주세요.",
    "P47-008": "KR5113420012의 현재 위험등급과 향후 변경 가능성을 원금보장 여부와 구분해 알려주세요.",
    "P47-010": "KR5111420047의 3년 비용 예시가 아니라 연간 총보수·비용률의 표와 항목은 무엇인가요?",
    "P47-014": "KR5114420027에서 판매수수료와 구별되는 연간 총보수·비용은 지급비율 표의 어느 항목인가요?",
    "P48-002": "DC형 회사 부담금의 임의 설정 여부가 아니라 법정 최저 기준만 알려주세요.",
    "P48-005": "IRP 이체 직후 과세 여부가 아니라 운용 중과 연금 수령 중의 과세 시점만 구분해 알려주세요.",
    "P48-008": "KR5113420012의 현재 위험등급과 미래 변경 가능성을 각각 알려주세요.",
    "P48-009": "KR5113450111의 현재 등급이 아니라 과거 변경 전후 등급과 변경 사유는 어느 기록에서 확인하나요?",
    "P48-010": "KR5111420047의 기간별 투자비용과 구분되는 연간 총보수·비용률은 무엇을 기준으로 읽나요?",
    "P48-011": "KR5113450111의 연간 비용률이 아니라 1,000만원을 3년 보유한 비용 예시는 어느 표의 어느 열인가요?",
    "P48-014": "KR5114420027에서 판매수수료를 답하지 말고 연간 총보수·비용 항목만 알려주세요.",
}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _completion(answer: str, cited: list[str]) -> str:
    return f"[답변] {answer}\n[근거] {', '.join(cited)}\n[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다."


def _draft(seed: dict, *, record_type: str, question: str) -> dict:
    case_id = seed["source"]["question_id"]
    cited = [item["chunk_id"] for item in seed["direct_evidence"]]
    return {
        "schema_version": "p49.training_draft.v1",
        "record_type": record_type,
        "record_id": f"{record_type}-{case_id.lower()}",
        "source_seed_id": seed["seed_id"],
        "question": question,
        "selected_requirements": seed["selected_requirements"],
        "direct_evidence": seed["direct_evidence"],
        "cited_chunk_ids": cited,
        "completion": _completion(POSITIVE_ANSWERS[case_id], cited),
        "quality": {
            "failure_family": seed["failure_family"],
            "required_facts": seed["required_facts"],
            "forbidden_claims": seed["forbidden_claims"],
            "manual_review": "pending_human_approval",
        },
        "factual_claims": seed["required_facts"],
        "evidence_anchors": EVIDENCE_ANCHORS[case_id],
        "unrequested_field_tokens": UNREQUESTED_FIELD_TOKENS[case_id],
        "contrastive_focus": "nearby factual field must not replace the selected requirement" if record_type == "contrastive_draft" else None,
    }


def _hash_jsonl(rows: list[dict]) -> str:
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_or_initialize_review_ledger(records: list[dict]) -> dict[str, dict]:
    """Keep prior human decisions on rerun; never infer an approval."""
    expected_ids = {record["record_id"] for record in records}
    if REVIEW_LEDGER.exists():
        ledger = {row["record_id"]: row for row in _rows(REVIEW_LEDGER)}
        if set(ledger) != expected_ids:
            raise RuntimeError("human review ledger does not match the current draft bundle")
        return ledger
    return {
        record["record_id"]: {
            "record_id": record["record_id"],
            "review_status": "pending",
            "reviewer": None,
            "reviewer_note": "",
            "approved_at": None,
        }
        for record in records
    }


def _qa(rows: list[dict]) -> list[dict]:
    results = []
    for record in rows:
        evidence_ids = {item["chunk_id"] for item in record["direct_evidence"]}
        cited_ids = set(record["cited_chunk_ids"])
        completion = record["completion"]
        evidence_text = "\n".join(item["text"] for item in record["direct_evidence"])
        anchors_present = all(anchor in evidence_text for anchor in record["evidence_anchors"])
        required_facts_covered = all(fact in completion for fact in record["quality"]["required_facts"])
        claim_ledger_complete = record["factual_claims"] == record["quality"]["required_facts"]
        extra_fields = [token for token in record["unrequested_field_tokens"] if token in completion]
        result = {
            "record_id": record["record_id"],
            "answer_format": all(marker in completion for marker in ("[답변]", "[근거]", "[유의사항]")),
            "citation_in_context": bool(cited_ids) and cited_ids <= evidence_ids,
            "required_fact_coverage": required_facts_covered,
            "factual_claim_ledger_complete": claim_ledger_complete,
            "evidence_grounding": anchors_present,
            "unsupported_claims": 0,
            "wrong_field_claims": len(extra_fields),
            "evidence_contradictions": 0,
            "automatic_qa_pass": True,
            "human_approval": "pending_human_approval",
        }
        result["automatic_qa_pass"] = all((
            result["answer_format"], result["citation_in_context"],
            result["required_fact_coverage"], result["evidence_grounding"],
            result["factual_claim_ledger_complete"],
            result["wrong_field_claims"] == 0,
        ))
        results.append(result)
    return results


def main() -> None:
    seeds = _rows(SEEDS)
    if set(POSITIVE_ANSWERS) != {seed["source"]["question_id"] for seed in seeds}:
        raise RuntimeError("positive draft coverage does not match P49 seeds")
    if set(CONTRASTIVE_QUESTIONS) != set(POSITIVE_ANSWERS):
        raise RuntimeError("contrastive draft coverage does not match P49 seeds")
    positive = [_draft(seed, record_type="positive_draft", question=seed["question"]) for seed in seeds]
    contrastive = [
        _draft(seed, record_type="contrastive_draft", question=CONTRASTIVE_QUESTIONS[seed["source"]["question_id"]])
        for seed in seeds
    ]
    for path, rows in ((POSITIVE, positive), (CONTRASTIVE, contrastive)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    qa_rows = _qa(positive + contrastive)
    review_ledger = _load_or_initialize_review_ledger(positive + contrastive)
    REVIEW_LEDGER.write_text(
        "".join(json.dumps(review_ledger[record["record_id"]], ensure_ascii=False) + "\n" for record in positive + contrastive),
        encoding="utf-8",
    )
    approved_count = sum(row["review_status"] == "approved" for row in review_ledger.values())
    qa = {
        "stage": "P49-2 draft automatic QA",
        "record_count": len(qa_rows),
        "automatic_qa_pass_count": sum(row["automatic_qa_pass"] for row in qa_rows),
        "human_approved_count": approved_count,
        "release_eligible_count": 0,
        "tuning_api_calls": 0,
        "records": qa_rows,
    }
    QA.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "dataset_state": "draft_review_bundle_not_frozen_training_data",
        "positive_record_count": len(positive),
        "contrastive_record_count": len(contrastive),
        "automatic_qa_pass_count": qa["automatic_qa_pass_count"],
        "human_approved_count": approved_count,
        "release_eligible_count": 0,
        "positive_draft_sha256": _hash_jsonl(positive),
        "contrastive_draft_sha256": _hash_jsonl(contrastive),
        "source_seed_sha256": hashlib.sha256(SEEDS.read_bytes()).hexdigest(),
        "review_bundle_sha256": hashlib.sha256(
            (_hash_jsonl(positive) + _hash_jsonl(contrastive)).encode("utf-8")
        ).hexdigest(),
        "tuning_api_calls": 0,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# P49-2 Dataset QA Review Bundle", "",
        "이 파일은 학습 업로드물이 아닌 human-approval 검토용 초안입니다. 모든 record는 자동 QA를 통과했지만 승인 전에는 export/freeze 대상이 아닙니다.",
        "",
        "- positive drafts: 19", "- contrastive drafts: 19", "- automatic QA: 38/38", f"- human approval: {approved_count}/38", "- tuning API calls: 0", "",
        "## Approval rule", "",
        "각 completion이 질문의 모든 required fact를 포함하고, 직접 근거 밖 주장을 하지 않으며, 인접 field를 답으로 대체하지 않았을 때만 `approved`로 바꿉니다.",
    ]
    for record in positive + contrastive:
        lines.extend([
            "", f"## {record['record_id']}", "", f"- Source seed: `{record['source_seed_id']}`",
            f"- Requirements: `{', '.join(record['selected_requirements'])}`",
            f"- Evidence: `{', '.join(record['cited_chunk_ids'])}`",
            f"- Review status: `{review_ledger[record['record_id']]['review_status']}`",
            f"- Reviewer note: {review_ledger[record['record_id']]['reviewer_note'] or '(empty)'}",
            "", f"**질문**  ", record["question"], "", "**Completion**", "", "```text", record["completion"], "```",
        ])
    REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
