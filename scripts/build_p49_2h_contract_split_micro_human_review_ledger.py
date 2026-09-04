"""Build a human evidence-first review ledger for the final P49-2H-3D v4 run.

This script is deliberately read-only with respect to candidate status: every
entry remains ``pending_human``.  It converts the evidence contract into a
reviewable checklist, not an automated approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_p49_2h_contract_split_micro_pilot import (  # noqa: E402
    validate_required_item_completeness,
    validate_subject_provenance,
)

RAW = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_raw_v4.jsonl"
VALIDATED = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_validated_v4.jsonl"
DEFAULT_LEDGER = ROOT / "evaluation/fine_tuning/p49_2h_contract_split_micro_human_review_ledger_v4.jsonl"
DEFAULT_REPORT = ROOT / "docs/p49_2h_contract_split_micro_human_review_v4.md"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def risk_focus(row: dict) -> list[str]:
    if row["outcome"] == "clarification_required":
        return [
            "사실 답변·근거·citation이 전혀 없는지",
            "목록이 missing_conditions 외 질문을 추가하지 않는지",
            "재질문이 실제로 필요한 최소 조건인지",
        ]
    if row["outcome"] == "bounded_answer":
        return [
            "supported requirement의 직접 사실이 답변 본문에 있는지",
            "unsupported_target이 유의사항의 한계 고지와 정확히 결속되는지",
            "미래값·예측값·투자권유가 본문에 생성되지 않았는지",
        ]
    requirement = row["requirements"][0]["canonical_requirement"]
    common = [
        "답변이 direct evidence의 requirement 범위만 말하는지",
        "질문하지 않은 유의사항·추천·정책 문구가 없는지",
        "literal quote와 chunk가 답변 사실을 직접 지지하는지",
    ]
    focused = {
        "pension_savings.tax_credit.limit": "연금저축 단독 600만원과 IRP 합산 900만원을 혼동하지 않는지",
        "ISA.transfer.deadline": "60일 기한 외 추가공제·최소이전금액을 덧붙이지 않는지",
        "ISA.transfer.additional_tax_credit": "10%·300만원 추가공제와 60일 기한을 혼동하지 않는지",
        "product.risk_grade.historical": "변경일·전후 등급·변경사유 범위를 모두 보존하는지",
        "product.total_fee": "총보수와 기간별 비용 예시를 혼동하지 않는지",
        "product.period_cost": "1·3·5·10년 표 범위가 총보수율로 바뀌지 않는지",
        "DC.early_withdrawal.required_documents": "6개월 이상 요양 조건과 신청양식·진단서가 함께 보존되는지",
    }.get(requirement)
    return ([focused] if focused else []) + common


def assistant_recommendation(row: dict) -> str:
    # This records a non-human evidence-first precheck.  It must never be
    # interpreted as human_review_status or acceptance.
    if row["outcome"] == "clarification_required":
        return "자동 계약상 근거·사실답변 없이 host missing_conditions만 조립됨: human 확인 권고"
    if row["outcome"] == "bounded_answer":
        return "지원 사실과 미지원 target 고지가 host-owned로 분리됨: human 확인 권고"
    return "host factual renderer와 direct literal quote가 결속됨: human 확인 권고"


def assistant_audit(row: dict) -> tuple[str, list[dict[str, str]]]:
    """Re-run the two known blind-spot rules without changing human state."""
    findings: list[dict[str, str]] = []
    for finding in validate_required_item_completeness(row):
        if finding.startswith("required_item_omission:"):
            omitted = finding.split(":", 1)[1]
            findings.append({
                "owner": "supported_omission", "severity": "blocking",
                "reason": f"질문이 요구한 서류 범위 중 다음 direct-evidence 항목이 completion에 없습니다: {omitted}.",
            })
    if "subject_provenance_mismatch" in validate_subject_provenance(row):
        findings.append({
            "owner": "product_subject_provenance_mismatch", "severity": "blocking",
            "reason": "질문의 명시적 상품 subject가 evidence source의 canonical product subject와 일치하지 않습니다.",
        })
    return ("fail_recommended" if findings else "pass_recommended", findings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--validated", type=Path, default=VALIDATED)
    parser.add_argument("--remediation-raw", type=Path, help="Optional new-candidate artifact that replaces matching micro_request_id rows for review only.")
    parser.add_argument("--remediation-validated", type=Path, help="Validation artifact paired with --remediation-raw.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    raw = read_jsonl(args.raw)
    original_candidate_ids = {row["micro_request_id"]: row["candidate_id"] for row in raw}
    validated = {row["candidate_id"]: row for row in read_jsonl(args.validated)}
    if len(raw) != 35 or {row["outcome"] for row in raw} != {"supported_answer", "clarification_required", "bounded_answer"}:
        raise RuntimeError("Human review ledger requires the complete 35-record v4 micro-pilot.")
    if any(validated.get(row["candidate_id"], {}).get("validation_status") != "pass" for row in raw):
        raise RuntimeError("Human review ledger requires automatic validation PASS for every v4 record.")
    replacements: dict[str, dict] = {}
    if bool(args.remediation_raw) != bool(args.remediation_validated):
        raise RuntimeError("Pass both --remediation-raw and --remediation-validated, or neither.")
    if args.remediation_raw:
        remediation = read_jsonl(args.remediation_raw)
        remediation_validated = {row["candidate_id"]: row for row in read_jsonl(args.remediation_validated)}
        if any(remediation_validated.get(row["candidate_id"], {}).get("validation_status") != "pass" for row in remediation):
            raise RuntimeError("Every remediation candidate must pass automatic validation before human review.")
        replacements = {row["micro_request_id"]: row for row in remediation}
        expected = {"P49-2H-3C-010", "P49-2H-3C-013"}
        if set(replacements) != expected:
            raise RuntimeError("This v4 remediation ledger requires exactly the two known blind-spot replacements.")
        raw = [replacements.get(row["micro_request_id"], row) for row in raw]

    ledger = []
    for row in raw:
        audit_recommendation, audit_findings = assistant_audit(row)
        evidence = [
            {"chunk_id": item["chunk_id"], "source_id": item["source_id"], "literal_quotes": row["required_gold_facts"][0]["evidence_literal_quotes"] if row["required_gold_facts"] else []}
            for item in row["direct_evidence"]
        ]
        ledger.append({
            "review_id": row["micro_request_id"],
            "candidate_id": row["candidate_id"],
            "coverage_cell": row["coverage_cell"],
            "outcome": row["outcome"],
            "question": row["question"],
            "requirements": row["requirements"],
            "evidence": evidence,
            "draft_completion": row["draft_completion"],
            "high_risk_review_focus": risk_focus(row),
            "assistant_evidence_first_precheck": audit_recommendation,
            "assistant_precheck_reason": assistant_recommendation(row),
            "assistant_evidence_first_findings": audit_findings,
            "review_status": "pending_human",
            "human_decision": None,
            "reviewer": None,
            "reviewed_at": None,
            "reviewer_note": None,
            "acceptance_status": "not_accepted",
            "supersedes_candidate_id": original_candidate_ids.get(row["micro_request_id"]) if row["micro_request_id"] in replacements else None,
        })

    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    args.ledger.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in ledger), encoding="utf-8")
    source_sha = hashlib.sha256(args.raw.read_bytes()).hexdigest()
    assistant_failures = sum(1 for row in ledger if row["assistant_evidence_first_precheck"] == "fail_recommended")
    report = "\n".join([
        "# P49-2H-3D v4 Human Evidence-First Review",
        "",
        f"- Candidate raw SHA-256: `{source_sha}`",
        "- Records: 35 (supported 15 / clarification 10 / bounded 10)",
        "- Automatic validation: 35/35 pass",
        "- Human status: **pending** — this ledger never approves or accepts a record.",
        f"- Assistant evidence-first precheck: {len(ledger) - assistant_failures}/{len(ledger)} pass recommended; {assistant_failures} blocking finding(s).",
        f"- Remediation replacements included: {len(replacements)}",
        "",
        "## Human final gate",
        "",
        "Approve only if factual error, evidence-scope violation, supported omission, unsupported invention, clarification over-questioning, recommendation/policy leakage, and frozen-seed mutation are all zero.",
        "",
        "Use the ledger row-by-row: read question → requirement → direct chunk/quotes → completion, then set `human_decision` to `pass` or `fail` with a concrete reviewer note.",
    ]) + "\n"
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(json.dumps({"records": len(ledger), "review_status": "pending_human", "assistant_failures": assistant_failures, "ledger_sha256": hashlib.sha256(args.ledger.read_bytes()).hexdigest()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
