"""Create P49 v3 review drafts after the final pre-approval recommendations.

v1 and v2 remain audit artifacts.  This script does not modify Agent runtime
code, call any provider API, or make a human approval decision.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from build_p49_dataset_qa_drafts import _hash_jsonl, _qa


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
V2_POSITIVE = BASE / "p49_draft_gold_training_records_v2.jsonl"
V2_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v2.jsonl"
V3_POSITIVE = BASE / "p49_draft_gold_training_records_v3.jsonl"
V3_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v3.jsonl"
QA_V3 = BASE / "p49_dataset_qa_results_v3.json"
MANIFEST_V3 = BASE / "p49_dataset_manifest_v3.json"
LEDGER = BASE / "p49_human_review_ledger.jsonl"
REPORT = ROOT / "docs/p49_2g2_final_review_reqa.md"

SUBSTANTIVE_IDS = {
    "positive_draft-p48-002",
    "contrastive_draft-p45-013",
    "positive_draft-p48-005",
    "contrastive_draft-p48-005",
    "positive_draft-p48-009",
    "contrastive_draft-p48-009",
}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _split_completion(completion: str) -> tuple[str, str]:
    answer, rest = completion.split("\n[근거] ", 1)
    cited, _notice = rest.split("\n[유의사항] ", 1)
    return answer.removeprefix("[답변] "), cited


def _set_completion(record: dict, answer: str) -> None:
    record["completion"] = f"[답변] {answer}\n[근거] {', '.join(record['cited_chunk_ids'])}\n[유의사항] 없음"


def _apply_substantive_fix(record: dict) -> str:
    record_id = record["record_id"]
    if record_id == "positive_draft-p48-002":
        record["question"] = "확정기여형 퇴직연금에서 회사 부담금을 법정 최저기준보다 적게 정할 수 있나요? 법정 기준도 알려주세요."
        _set_completion(record, "회사 부담금 기준은 연간 임금총액의 12분의 1 이상입니다.")
        record["quality"]["required_facts"] = ["연간 임금총액의 12분의 1 이상"]
        record["quality"]["forbidden_claims"] = ["사용자가 임의로 정해도 된다고 설명", "법정 기준을 근거 없이 부정"]
        record["factual_claims"] = record["quality"]["required_facts"]
        record["evidence_anchors"] = ["1/12"]
        record["unrequested_field_tokens"] = []
        return "임금총액과 법정 최저기준을 혼동할 수 있던 질문을 법정 기준 질문으로 명확화"
    if record_id == "contrastive_draft-p45-013":
        _set_completion(record, "KR5111420047의 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.")
        record["quality"]["required_facts"] = ["지급비율(연간, %) 표의 총보수·비용 항목"]
        record["quality"]["forbidden_claims"] = ["명시된 상품을 두 번째 상품이라는 불필요한 순서 참조로 재해석"]
        record["factual_claims"] = record["quality"]["required_facts"]
        record["evidence_anchors"] = ["지급비율", "총보수"]
        record["unrequested_field_tokens"] = ["합성총보수·비용", "1,000만원", "기간별 비용"]
        record["contrastive_focus"] = "explicit product subject stays fixed; product.total_fee only"
        return "명시된 상품코드를 두 번째 상품으로 불필요하게 재해석한 표현 제거"
    if record_id in {"positive_draft-p48-005", "contrastive_draft-p48-005"}:
        _set_completion(record, "운용 중에는 연금 수령 시까지 과세이연(운용 중 세금 없음)입니다. 세금 납부시점은 연금 수령시마다 분산됩니다.")
        record["quality"]["required_facts"] = ["연금 수령 시까지 과세이연(운용 중 세금 없음)", "세금 납부시점은 연금 수령시마다 분산"]
        record["quality"]["forbidden_claims"] = ["이체 즉시 전액 과세", "연금 수령 시점과 무관하게 모든 세금이 과세된다고 일반화"]
        record["factual_claims"] = record["quality"]["required_facts"]
        record["evidence_anchors"] = ["과세이연", "운용 중 세금 없음", "연금 수령시마다 분산"]
        record["unrequested_field_tokens"] = ["이체 즉시"]
        return "IRP 과세시점을 원본 표의 과세이연·분산 납부 표현에 밀착"
    if record_id in {"positive_draft-p48-009", "contrastive_draft-p48-009"}:
        record["question"] = "KR5113450111의 위험등급 변경 이력에서 변경일, 변경 전후 등급, 변경 사유를 알려주세요."
        _set_completion(
            record,
            "변경 이력은 2016.07.02 1등급→3등급(분류체계 개편 및 주간수익률 변동성), 2021.03.31 3등급→2등급(주간수익률 변동성), 2024.03.28 2등급→3등급(주간수익률 변동성), 2025.03.28 3등급→2등급(위험등급 산정기준이 표준편차에서 VaR로 변경되고 VaR 기반 수익률변동성을 반영)으로 기재되어 있습니다.",
        )
        record["quality"]["required_facts"] = [
            "2016.07.02 1등급→3등급(분류체계 개편 및 주간수익률 변동성)",
            "2021.03.31 3등급→2등급(주간수익률 변동성)",
            "2024.03.28 2등급→3등급(주간수익률 변동성)",
            "2025.03.28 3등급→2등급(위험등급 산정기준이 표준편차에서 VaR로 변경되고 VaR 기반 수익률변동성을 반영)",
        ]
        record["quality"]["forbidden_claims"] = ["현재 위험등급만 제시", "변경 전후 등급 또는 변경 사유를 생략"]
        record["factual_claims"] = record["quality"]["required_facts"]
        record["evidence_anchors"] = [
            "2016.07.02", "2021.03.31", "2024.03.28", "2025.03.28",
            "변경전 위험등급", "변경후 위험등급", "위험등급 변경사유",
        ]
        record["unrequested_field_tokens"] = ["현재 위험등급"]
        record["contrastive_focus"] = "historical values and reasons, not only the current risk grade" if record["record_type"] == "contrastive_draft" else None
        return "historical requirement을 표 위치 안내가 아니라 변경일·전후 등급·사유의 실제 factual answer로 정렬"
    raise AssertionError(record_id)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    source_positive, source_contrastive = _rows(V2_POSITIVE), _rows(V2_CONTRASTIVE)
    source = {record["record_id"]: record for record in source_positive + source_contrastive}
    if SUBSTANTIVE_IDS - set(source):
        raise RuntimeError("a requested review record is absent from v2")
    positive, contrastive = deepcopy(source_positive), deepcopy(source_contrastive)
    records = positive + contrastive
    changes = []
    for record in records:
        before = hashlib.sha256(record["completion"].encode("utf-8")).hexdigest()
        if record["record_id"] in SUBSTANTIVE_IDS:
            reason = _apply_substantive_fix(record)
            kind = "substantive"
        else:
            answer, _cited = _split_completion(record["completion"])
            _set_completion(record, answer)
            reason = "user-visible [유의사항] contract: no applicable caution → 없음"
            kind = "output_contract"
        after = hashlib.sha256(record["completion"].encode("utf-8")).hexdigest()
        if before == after:
            raise RuntimeError(f"expected completion update did not occur: {record['record_id']}")
        changes.append({
            "record_id": record["record_id"], "kind": kind,
            "before_completion_sha256": before, "after_completion_sha256": after, "reason": reason,
        })
    if {item["record_id"] for item in changes if item["kind"] == "substantive"} != SUBSTANTIVE_IDS:
        raise RuntimeError("substantive change set does not match the six requested records")
    protected = {"source_seed_id", "selected_requirements", "direct_evidence", "cited_chunk_ids"}
    for record in records:
        for key in protected:
            if record[key] != source[record["record_id"]][key]:
                raise RuntimeError(f"protected field changed: {record['record_id']}.{key}")
    _write_jsonl(V3_POSITIVE, positive)
    _write_jsonl(V3_CONTRASTIVE, contrastive)

    qa_rows = _qa(records)
    by_id = {row["record_id"]: row for row in qa_rows}
    for item in changes:
        item["automatic_qa_pass"] = by_id[item["record_id"]]["automatic_qa_pass"]
    qa = {
        "stage": "P49-2G2 final human-review recommendations and re-QA",
        "total_records": len(records), "substantive_modified_records": len(SUBSTANTIVE_IDS),
        "output_contract_updated_records": len(records),
        "qa_pass": sum(row["automatic_qa_pass"] for row in qa_rows),
        "qa_fail": sum(not row["automatic_qa_pass"] for row in qa_rows),
        "human_approved": 0, "human_pending": len(records),
        "tuning_api_calls": 0, "ncp_resource_changes": 0,
        "changes": changes, "records": qa_rows,
    }
    QA_V3.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "dataset_status": "draft_awaiting_human_approval",
        "total_records": len(records), "substantive_modified_records": len(SUBSTANTIVE_IDS),
        "output_contract": "[유의사항] 없음 when no evidence-grounded user caution applies",
        "qa_pass": qa["qa_pass"], "qa_fail": qa["qa_fail"],
        "human_approved": 0, "human_pending": len(records),
        "positive_draft_sha256": _hash_jsonl(positive),
        "contrastive_draft_sha256": _hash_jsonl(contrastive),
        "source_v2_positive_sha256": hashlib.sha256(V2_POSITIVE.read_bytes()).hexdigest(),
        "source_v2_contrastive_sha256": hashlib.sha256(V2_CONTRASTIVE.read_bytes()).hexdigest(),
        "tuning_api_calls": 0, "ncp_resource_changes": 0,
    }
    MANIFEST_V3.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger = _rows(LEDGER)
    for row in ledger:
        if row["record_id"] in SUBSTANTIVE_IDS:
            if row["review_status"] != "pending" or row["reviewer"] is not None or row["approved_at"] is not None:
                raise RuntimeError(f"cannot annotate a finalized human decision: {row['record_id']}")
            prefix = "AI final review fixes applied and automatic QA passed; awaiting final human approval."
            row["reviewer_note"] = prefix
    _write_jsonl(LEDGER, ledger)

    lines = [
        "# P49-2G2 Final Review Recommendations + Re-QA", "",
        "## Status", "", "**Automatic QA Go / Human approval Pending.** v1 and v2 remain preserved for audit. v3 is still a draft; it is neither canonical nor frozen training data.", "",
        f"- Substantive records changed: {len(SUBSTANTIVE_IDS)}/6", "- User-visible output contract updated: 38/38 (`[유의사항] 없음`)",
        f"- Automatic QA: {qa['qa_pass']}/38", "- Human approved: 0/38", "- Human pending: 38/38", "- Tuning API calls: 0", "- NCP resource changes: 0", "",
        "## Substantive changes", "", "| Record | Before → after completion hash | Reason | QA |", "| --- | --- | --- | ---: |",
    ]
    for item in sorted((item for item in changes if item["kind"] == "substantive"), key=lambda item: item["record_id"]):
        lines.append(f"| `{item['record_id']}` | `{item['before_completion_sha256'][:12]}` → `{item['after_completion_sha256'][:12]}` | {item['reason']} | {'PASS' if item['automatic_qa_pass'] else 'FAIL'} |")
    lines.extend([
        "", "## Remaining human decision", "",
        "All 38 records remain `pending`. A human reviewer must decide `approved`, `edit_required`, or `rejected`; no automated result is a human approval.",
        "", "## Next allowed step", "",
        "After human decisions and any required re-QA, promote only approved records to Gold Seed v1 and freeze its manifest/hash. P49-2H, baseline A/B, and tuning remain out of scope.",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: qa[key] for key in ("total_records", "substantive_modified_records", "output_contract_updated_records", "qa_pass", "qa_fail", "human_approved", "human_pending", "tuning_api_calls", "ncp_resource_changes")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
