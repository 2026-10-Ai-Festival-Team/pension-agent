"""Repair only the three I1A host-owned surfaces that collide in the 608 pool."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_p49_2h_4d_i1_supported_preflight as preflight
from scripts import run_p49_2h_4c_execution_bridge as bridge

SOURCE = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_manifest_v2.jsonl"
OUTPUT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_manifest_v4_i1a.jsonl"
REPORT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_final_host_question_preflight_v6_i1a_surface_repair.json"
ARTIFACT_ID = "P49-2H-4D-I1A-surface-repair-v2"

# Each replacement changes only a reviewed renderer family.  The semantic
# request, Q1A cell, subject, evidence, and answer-completeness binding remain
# verbatim from the authoritative 48-row manifest.
REVISIONS = {
    "P49-2H-4D-I-SUP-0001": "confirmation",
    "P49-2H-4D-I-SUP-0009": "direct",
    "P49-2H-4D-I-SUP-0032": "direct",
}
IMMUTABLE_FIELDS = (
    "remediation_request_id",
    "coverage_cell",
    "q1a_quota_cell",
    "target_outcome",
    "canonical_requirement",
    "subject",
    "evidence_chunk_ids",
    "source_ids",
    "semantic_slots",
    "supported_answer_completeness",
)


def write(path: Path, value: Any, *, jsonl: bool = False) -> None:
    if path.exists():
        raise FileExistsError(path)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in value) if jsonl else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def repaired_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) != 48:
        raise ValueError("I1A surface repair requires the authoritative 48-row I manifest")
    by_id = {row["remediation_request_id"]: row for row in rows}
    if set(REVISIONS) - set(by_id):
        raise ValueError("dedup repair IDs are not present in the authoritative I manifest")
    repaired = deepcopy(rows)
    for row in repaired:
        request_id = row["remediation_request_id"]
        if request_id not in REVISIONS:
            continue
        renderer = row.get("host_question_renderer", {})
        if not renderer.get("renderer_id") or not renderer.get("family"):
            raise ValueError(f"missing host renderer control for {request_id}")
        renderer["family"] = REVISIONS[request_id]
        row["host_question_surface_artifact_id"] = ARTIFACT_ID
        row["host_question_surface_revision"] = "dedup_only"
    for before, after in zip(rows, repaired):
        for field in IMMUTABLE_FIELDS:
            if before.get(field) != after.get(field):
                raise AssertionError(f"immutable I control changed for {before['remediation_request_id']}: {field}")
        changed = set(after) ^ set(before)
        if before["remediation_request_id"] in REVISIONS:
            if changed != {"host_question_surface_artifact_id", "host_question_surface_revision"}:
                raise AssertionError("unexpected surface-repair field change")
            if {
                key: value
                for key, value in before["host_question_renderer"].items()
                if key != "family"
            } != {
                key: value
                for key, value in after["host_question_renderer"].items()
                if key != "family"
            }:
                raise AssertionError("renderer identity changed during surface repair")
        elif before != after:
            raise AssertionError(f"non-colliding row changed: {before['remediation_request_id']}")
    return repaired


def main() -> None:
    source = bridge.read_jsonl(SOURCE)
    rows = repaired_rows(source)
    pool = [row for row in bridge.read_jsonl(preflight.POOL) if row.get("validation_status") == "pass"]
    if len(pool) != 608:
        raise ValueError("I1A surface repair requires the frozen H-promoted 608 comparison pool")
    report = preflight.preflight(rows, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    revised_questions = {
        row["remediation_request_id"]: row["question"]
        for row in report["questions"]
        if row["remediation_request_id"] in REVISIONS
    }
    report.update(
        {
            "artifact_id": ARTIFACT_ID,
            "source_manifest": SOURCE.name,
            "surface_repair_candidate_ids": list(REVISIONS),
            "surface_repair_families": REVISIONS,
            "surface_repair_questions": revised_questions,
            "external_hcx_calls": 0,
            "i_live_status": "HOLD_pending_human_review_of_strict_preflight",
        }
    )
    write(OUTPUT, rows, jsonl=True)
    write(REPORT, report)
    print(json.dumps({"external_hcx_calls": 0, "repaired": len(REVISIONS), "preflight_pass": report["live_execution_allowed"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
