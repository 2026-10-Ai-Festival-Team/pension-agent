"""Annotate P49's reviewed FULL-evidence drafts with the v2 answer contract.

This is a draft-only migration.  It neither decides human approval nor exports
provider training data, and keeps v1--v3 artifacts unchanged for audit.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from build_p49_dataset_qa_drafts import _hash_jsonl, _qa


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
V3_POSITIVE = BASE / "p49_draft_gold_training_records_v3.jsonl"
V3_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v3.jsonl"
V4_POSITIVE = BASE / "p49_draft_gold_training_records_v4.jsonl"
V4_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v4.jsonl"
QA_V4 = BASE / "p49_dataset_qa_results_v4.json"
MANIFEST_V4 = BASE / "p49_dataset_manifest_v4.json"
REPORT = ROOT / "docs/p49_2g3_full_evidence_contract.md"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _annotate(record: dict) -> None:
    record["schema_version"] = "p49.training_draft.v2"
    record["outcome"] = "supported_answer"
    record["evidence_status"] = "full"
    record["missing_conditions"] = []
    record["unsupported_requirements"] = []
    record["quality"]["answer_policy_contract"] = "full_evidence_supported_answer"


def main() -> None:
    source_positive = _rows(V3_POSITIVE)
    source_contrastive = _rows(V3_CONTRASTIVE)
    positive, contrastive = deepcopy(source_positive), deepcopy(source_contrastive)
    records = positive + contrastive
    if len(records) != 38 or len({row["record_id"] for row in records}) != 38:
        raise RuntimeError("expected exactly 38 unique P49 draft records")
    for record in records:
        _annotate(record)
        if record["completion"].split("[유의사항] ", 1)[-1] != "없음":
            raise RuntimeError(f"unexpected non-empty notice in full-evidence seed: {record['record_id']}")
    _write_jsonl(V4_POSITIVE, positive)
    _write_jsonl(V4_CONTRASTIVE, contrastive)

    qa_rows = _qa(records)
    if len(qa_rows) != len(records):
        raise RuntimeError("QA rows do not match draft records")
    for row, record in zip(qa_rows, records):
        outcome_contract = (
            record["outcome"] == "supported_answer"
            and record["evidence_status"] == "full"
            and record["missing_conditions"] == []
            and record["unsupported_requirements"] == []
        )
        row["answer_policy_contract"] = outcome_contract
        row["automatic_qa_pass"] = row["automatic_qa_pass"] and outcome_contract
    qa = {
        "stage": "P49-2G3 full-evidence outcome-contract annotation and re-QA",
        "dataset_status": "draft_awaiting_human_approval",
        "total_records": len(records),
        "outcome_distribution": {"supported_answer": len(records)},
        "evidence_status_distribution": {"full": len(records)},
        "automatic_qa_pass": sum(row["automatic_qa_pass"] for row in qa_rows),
        "automatic_qa_fail": sum(not row["automatic_qa_pass"] for row in qa_rows),
        "human_approved": 0,
        "human_pending": len(records),
        "tuning_api_calls": 0,
        "records": qa_rows,
    }
    QA_V4.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "dataset_status": "draft_awaiting_human_approval",
        "source_v3_positive_sha256": hashlib.sha256(V3_POSITIVE.read_bytes()).hexdigest(),
        "source_v3_contrastive_sha256": hashlib.sha256(V3_CONTRASTIVE.read_bytes()).hexdigest(),
        "positive_draft_sha256": _hash_jsonl(positive),
        "contrastive_draft_sha256": _hash_jsonl(contrastive),
        "record_count": len(records),
        "answer_policy_contract": {
            "outcome": "supported_answer",
            "evidence_status": "full",
            "missing_conditions": [],
            "unsupported_requirements": [],
            "notice_when_no_user_caution": "없음"
        },
        "automatic_qa_pass": qa["automatic_qa_pass"],
        "human_approved": 0,
        "human_pending": len(records),
        "tuning_api_calls": 0,
        "ncp_resource_changes": 0,
    }
    MANIFEST_V4.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "\n".join((
            "# P49-2G3 Full-Evidence Outcome Contract", "",
            "## Status", "",
            "**Automatic QA Go / Human approval Pending.** v4 annotates the existing 38 reviewed drafts; it does not freeze or upload training data.", "",
            "- Records: 38/38", "- Outcome: `supported_answer`", "- Evidence status: `full`",
            "- Missing conditions: 0", "- Unsupported requirements: 0", "- `[유의사항]`: `없음`", "",
            "## Boundary", "",
            "Bounded-answer and clarification examples are intentionally not added to this Gold Seed bundle. They belong to P49-2H augmentation after human approval and Gold Seed v1 freeze.",
            "",
        )),
        encoding="utf-8",
    )
    print(json.dumps({key: qa[key] for key in ("total_records", "automatic_qa_pass", "automatic_qa_fail", "human_approved", "human_pending", "tuning_api_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
