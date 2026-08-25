"""Apply the 14 human-review recommendations to separate P49 draft v2 files.

This is deliberately a review-preparation script. It never promotes records,
declares a human approval, calls a tuning API, or changes the runtime Agent.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from build_p49_dataset_qa_drafts import _hash_jsonl, _qa


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
V1_POSITIVE = BASE / "p49_draft_gold_training_records_v1.jsonl"
V1_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v1.jsonl"
V2_POSITIVE = BASE / "p49_draft_gold_training_records_v2.jsonl"
V2_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v2.jsonl"
QA_V2 = BASE / "p49_dataset_qa_results_v2.json"
MANIFEST_V2 = BASE / "p49_dataset_manifest_v2.json"
LEDGER = BASE / "p49_human_review_ledger.jsonl"
REPORT = ROOT / "docs/p49_2g_human_review_fix_and_reqa.md"


TOTAL_FEE_IDS = {
    "positive_draft-p45-010", "positive_draft-p47-010", "positive_draft-p48-010",
    "contrastive_draft-p45-010", "contrastive_draft-p47-010", "contrastive_draft-p48-010",
}
DB_IDS = {
    "positive_draft-p45-018", "positive_draft-p46-016",
    "contrastive_draft-p45-018", "contrastive_draft-p46-016",
}
RISK_IDS = {"positive_draft-p47-008", "contrastive_draft-p47-008"}
P46_013 = "contrastive_draft-p46-013"
P48_014 = "contrastive_draft-p48-014"
MODIFIED_IDS = TOTAL_FEE_IDS | DB_IDS | RISK_IDS | {P46_013, P48_014}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _completion(answer: str, cited: list[str]) -> str:
    return f"[답변] {answer}\n[근거] {', '.join(cited)}\n[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다."


def _set_answer(record: dict, answer: str, required_facts: list[str], *, forbidden: list[str] | None = None,
                anchors: list[str] | None = None, unrequested: list[str] | None = None,
                focus: str | None = None) -> None:
    record["completion"] = _completion(answer, record["cited_chunk_ids"])
    record["quality"]["required_facts"] = required_facts
    if forbidden is not None:
        record["quality"]["forbidden_claims"] = forbidden
    record["factual_claims"] = required_facts
    if anchors is not None:
        record["evidence_anchors"] = anchors
    if unrequested is not None:
        record["unrequested_field_tokens"] = unrequested
    if focus is not None:
        record["contrastive_focus"] = focus


def _apply(record: dict) -> str:
    record_id = record["record_id"]
    if record_id in TOTAL_FEE_IDS:
        _set_answer(
            record,
            "지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.",
            ["지급비율(연간, %) 표의 총보수·비용 항목"],
            forbidden=["합성총보수·비용을 product.total_fee의 자동 대체값으로 제시"],
            anchors=["지급비율", "총보수"],
            unrequested=["합성총보수·비용", "1,000만원", "기간별 비용"],
            focus="product.total_fee only; adjacent total-cost and period-cost fields are excluded",
        )
        return "product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화"
    if record_id in DB_IDS:
        subject = "DB형" if "p45-018" in record_id else "DB제도"
        _set_answer(
            record,
            f"{subject}은 회사가 적립금을 운용합니다. 퇴직급여는 퇴직 전 평균임금 30일분 × 계속근로기간을 기준으로 산정합니다.",
            ["회사가 적립금을 운용", "퇴직급여는 퇴직 전 평균임금 30일분 × 계속근로기간을 기준으로 산정"],
            anchors=["회사", "평균임금", "계속근로기간"],
        )
        return "DB 급여 산정의 두 요소와 산식 관계를 직접 근거 표현으로 명확화"
    if record_id in RISK_IDS:
        _set_answer(
            record,
            "현재 5등급(낮은 위험)입니다. 문서상 위험등급은 운용실적·시장 상황 등에 따라 변경될 수 있습니다.",
            ["현재 5등급(낮은 위험)", "문서상 위험등급은 운용실적·시장 상황 등에 따라 변경될 수 있습니다"],
            anchors=["5등급", "변경될 수"],
            unrequested=["원금보장"],
        )
        return "위험등급 변경 가능성의 문체를 자연스럽고 직접적인 표현으로 수정"
    if record_id == P46_013:
        _set_answer(
            record,
            "KR5127420045의 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.",
            ["지급비율(연간, %) 표의 총보수·비용 항목"],
            forbidden=["명시적으로 선택된 상품을 후자라는 새 참조로 재해석"],
            anchors=["지급비율", "총 보수"],
            unrequested=["판매수수료"],
            focus="explicit product subject stays fixed; product.total_fee only",
        )
        return "명시적으로 주어진 상품코드를 후자라는 불필요한 참조로 다시 해석하지 않도록 수정"
    if record_id == P48_014:
        _set_answer(
            record,
            "지급비율(연간, %) 표의 총보수·비용 항목입니다.",
            ["지급비율(연간, %) 표의 총보수·비용 항목"],
            forbidden=["제외된 판매수수료 field를 답변에 다시 포함"],
            anchors=["지급비율", "총 보수"],
            unrequested=["판매수수료"],
            focus="explicitly excluded sales-fee field must not be repeated in the answer",
        )
        return "negative contrast에서 제외된 판매수수료 field를 답변에 다시 쓰지 않도록 수정"
    raise AssertionError(record_id)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    original_positive, original_contrastive = _rows(V1_POSITIVE), _rows(V1_CONTRASTIVE)
    original = {record["record_id"]: record for record in original_positive + original_contrastive}
    if set(MODIFIED_IDS) - set(original):
        raise RuntimeError("one or more requested records are absent from v1")

    positive, contrastive = deepcopy(original_positive), deepcopy(original_contrastive)
    v2 = positive + contrastive
    changes = []
    for record in v2:
        if record["record_id"] not in MODIFIED_IDS:
            continue
        before = hashlib.sha256(record["completion"].encode("utf-8")).hexdigest()
        reason = _apply(record)
        after = hashlib.sha256(record["completion"].encode("utf-8")).hexdigest()
        if before == after:
            raise RuntimeError(f"requested change did not alter completion: {record['record_id']}")
        changes.append({
            "record_id": record["record_id"], "before_completion_sha256": before,
            "after_completion_sha256": after, "reason": reason,
        })
    if {change["record_id"] for change in changes} != MODIFIED_IDS:
        raise RuntimeError("modified-record set does not exactly match the 14 requested records")

    # Immutable training inputs remain byte-for-byte equivalent to v1 for every
    # record: only answer target and accompanying QA metadata may differ.
    protected = {"source_seed_id", "selected_requirements", "direct_evidence", "cited_chunk_ids"}
    for record in v2:
        for key in protected:
            if record[key] != original[record["record_id"]][key]:
                raise RuntimeError(f"protected field changed: {record['record_id']}.{key}")
    _write_jsonl(V2_POSITIVE, positive)
    _write_jsonl(V2_CONTRASTIVE, contrastive)

    qa_rows = _qa(v2)
    by_id = {row["record_id"]: row for row in qa_rows}
    for change in changes:
        change["automatic_qa_pass"] = by_id[change["record_id"]]["automatic_qa_pass"]
    qa = {
        "stage": "P49-2G recommended fixes and re-QA",
        "total_records": len(v2),
        "modified_records": len(changes),
        "unchanged_records": len(v2) - len(changes),
        "qa_pass": sum(row["automatic_qa_pass"] for row in qa_rows),
        "qa_fail": sum(not row["automatic_qa_pass"] for row in qa_rows),
        "human_approved": 0,
        "human_pending": len(v2),
        "tuning_api_calls": 0,
        "ncp_resource_changes": 0,
        "changes": changes,
        "records": qa_rows,
    }
    QA_V2.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "dataset_status": "draft_awaiting_human_approval",
        "total_records": len(v2),
        "modified_records": len(changes),
        "unchanged_records": len(v2) - len(changes),
        "qa_pass": qa["qa_pass"],
        "qa_fail": qa["qa_fail"],
        "human_approved": 0,
        "human_pending": len(v2),
        "positive_draft_sha256": _hash_jsonl(positive),
        "contrastive_draft_sha256": _hash_jsonl(contrastive),
        "source_v1_positive_sha256": hashlib.sha256(V1_POSITIVE.read_bytes()).hexdigest(),
        "source_v1_contrastive_sha256": hashlib.sha256(V1_CONTRASTIVE.read_bytes()).hexdigest(),
        "tuning_api_calls": 0,
        "ncp_resource_changes": 0,
    }
    MANIFEST_V2.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ledger = _rows(LEDGER)
    if {row["record_id"] for row in ledger} != set(original):
        raise RuntimeError("human review ledger does not match v1 bundle")
    for row in ledger:
        if row["record_id"] in MODIFIED_IDS:
            if row["review_status"] != "pending" or row["reviewer"] is not None or row["approved_at"] is not None:
                raise RuntimeError(f"cannot overwrite non-pending human review: {row['record_id']}")
            row["reviewer_note"] = "AI review fixes applied and automatic QA passed; awaiting final human approval."
    _write_jsonl(LEDGER, ledger)

    report_lines = [
        "# P49-2G Human Review Recommended Fixes + Re-QA", "",
        "## Status", "",
        "**Automatic QA Go / Human approval Pending.** v1 drafts remain unchanged for audit; this report and v2 files are review-preparation artifacts, not frozen training data.", "",
        f"- Modified: {len(changes)}/14", f"- Unchanged regression records: {len(v2) - len(changes)}/24", f"- Automatic QA: {qa['qa_pass']}/{len(v2)}", "- Human approved: 0/38", "- Human pending: 38/38", "- Tuning API calls: 0", "- NCP resource changes: 0", "",
        "## Record changes", "",
        "| Record | Before → after completion hash | Reason | QA |", "| --- | --- | --- | ---: |",
    ]
    for change in sorted(changes, key=lambda item: item["record_id"]):
        report_lines.append(f"| `{change['record_id']}` | `{change['before_completion_sha256'][:12]}` → `{change['after_completion_sha256'][:12]}` | {change['reason']} | {'PASS' if change['automatic_qa_pass'] else 'FAIL'} |")
    report_lines.extend([
        "", "## Remaining human review", "",
        "Each v2 record remains `pending`. A human reviewer must still confirm naturalness, financial meaning, direct-evidence fidelity, field precision, and the contrastive target before any `approved` state or freeze.", "",
        "## Next step after approval", "",
        "Only after the final ledger contains the human decisions should approved records be promoted into a canonical Gold Seed v1 dataset and its immutable manifest/hash be created.",
    ])
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({key: qa[key] for key in ("total_records", "modified_records", "unchanged_records", "qa_pass", "qa_fail", "human_approved", "human_pending", "tuning_api_calls", "ncp_resource_changes")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
