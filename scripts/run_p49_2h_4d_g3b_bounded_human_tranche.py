"""Execute the guarded G3-B human-owned bounded residual tranche.

This module makes no semantic-policy changes.  It joins the two authoritative
G3-B review artifacts, reuses the frozen 4B -> v4 adapter and execution bridge,
and creates new additive artifacts only when every strict gate is closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge
from scripts.run_p49_2h_full_adapter import semantic_question_findings


Q1A = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3_q1a_full_allocation_reconstruction_v1.json"
REVIEW_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_authoritative_review_manifest_v1.jsonl"
HUMAN_SIDECAR = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_human_final_questions_v1.jsonl"
SOURCE_MANIFEST = bridge.REMEDIATION_MANIFEST
BASELINE_555 = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3a_cumulative_comparison_pool_v1.jsonl"

APPROVED = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_human_approved_v1.jsonl"
PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_human_approved_preflight_v1.json"
TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_trace_v1.jsonl"
CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_candidates_v1.jsonl"
AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_audit_v1.json"
PROMOTION = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_promotion_v1.jsonl"
PROMOTION_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_promotion_audit_v1.json"
PROMOTED_POOL = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_cumulative_comparison_pool_v1.jsonl"
H_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_residual_manifest_v1.jsonl"
H_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_h_clarification_residual_preflight_v1.json"
I_MANIFEST = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_residual_manifest_v1.jsonl"
I_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_i_supported_residual_preflight_v1.json"

V2_APPROVED = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_human_approved_v2.jsonl"
V2_PREFLIGHT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_human_approved_preflight_v2.json"
V2_TRACE = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_trace_v2.jsonl"
V2_CANDIDATES = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_candidates_v2.jsonl"
V2_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_live_audit_v2.json"
V2_PROMOTION = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_promotion_v2.jsonl"
V2_PROMOTION_AUDIT = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_promotion_audit_v2.json"
V2_PROMOTED_POOL = ROOT / "evaluation/fine_tuning/p49_2h_4d_g3b_bounded_cumulative_comparison_pool_v2.jsonl"

TOTAL_CREDIT_BEFORE = 499
BOUNDED_CREDIT_BEFORE = 75
TOTAL_TARGET = 600
BOUNDED_TARGET = 102
G3B_EXPECTED_BY_CELL = {
    "D12-Q18-bounded_answer": 5,
    "D17-Q12-bounded_answer": 1,
    "D17-Q17-bounded_answer": 4,
    "D18-Q17-bounded_answer": 5,
    "D20-Q18-bounded_answer": 5,
    "D30-Q12-bounded_answer": 1,
    "D30-Q17-bounded_answer": 6,
}
REVIEW_SEMANTIC_FIELDS = (
    "coverage_cell",
    "subject",
    "target_type",
    "unsupported_target",
    "temporal_scope",
    "allowed_fields",
    "forbidden_fields",
    "evidence_chunk_ids",
    "source_ids",
)
HUMAN_REVISIONS_V2 = {
    # These are user-directed editorial revisions.  They are intentionally
    # limited to the five rows that the frozen validator rejected; the other
    # 22 user-approved strings are retained byte-for-byte from v1.
    "P49-2H-4D-G3B-REVIEW-0003": "ISA 만기자금 이전 혜택을 계산하려는데, 내년에 적용될 추가 세액공제 한도가 얼마인지 지금 확인할 수 있어?",
    "P49-2H-4D-G3B-REVIEW-0005": "ISA 만기자금을 연금계좌로 옮길 때, 앞으로 적용될 추가 세액공제 한도가 얼마인지 확인할 수 있어?",
    "P49-2H-4D-G3B-REVIEW-0010": "이 상품의 현재 위험등급을 봤는데, 앞으로도 같은 등급으로 그대로 간다고 봐도 되는 거야?",
    "P49-2H-4D-G3B-REVIEW-0018": "이 상품 비용을 미리 계산하려는데, 앞으로 적용될 총보수율이 몇 퍼센트인지도 지금 확인할 수 있어?",
    "P49-2H-4D-G3B-REVIEW-0019": "이 상품의 지금 총보수율이 나와 있는데, 앞으로도 같은 비율이 적용된다고 봐도 되는 거야?",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing G3-B artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_new_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing G3-B artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def review_rows_with_ordinal(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive the missing review-side ordinal deterministically from its ID.

    The authoritative review manifest has no ``cell_ordinal`` field; its
    monotonically ordered review IDs are the source-side ordering authority.
    The derived ordinal is used only to make the required three-part join key
    explicit and is retained in the new artifact.
    """
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cell[row["coverage_cell"]].append(row)
    enriched: list[dict[str, Any]] = []
    for cell, values in sorted(by_cell.items()):
        for ordinal, row in enumerate(sorted(values, key=lambda item: item["request_id"]), start=1):
            item = deepcopy(row)
            item["cell_ordinal"] = ordinal
            enriched.append(item)
    return sorted(enriched, key=lambda row: row["request_id"])


def q1a_residuals(q1a: dict[str, Any], lane: str) -> list[dict[str, Any]]:
    return [
        deepcopy(row) for row in q1a["rows"]
        if row["lane"] == lane and row["deficit"] > 0
    ]


def q1a_bounded_deficit_by_cell(q1a: dict[str, Any]) -> dict[str, int]:
    return {
        row["coverage_cell"]: row["deficit"]
        for row in q1a_residuals(q1a, "bounded_answer")
    }


def source_semantic_value(source: dict[str, Any], field: str) -> Any:
    if field in {"allowed_fields", "forbidden_fields", "target_type", "unsupported_target", "temporal_scope"}:
        return source["semantic_slots"][field]
    return source[field]


def assert_review_matches_source(review: dict[str, Any], source: dict[str, Any]) -> None:
    if source["coverage_cell"] != review["coverage_cell"]:
        raise ValueError(f"review/source coverage cell mismatch for {review['request_id']}")
    if source["target_outcome"] != "bounded_answer":
        raise ValueError(f"review source is not bounded_answer: {review['request_id']}")
    for field in REVIEW_SEMANTIC_FIELDS:
        if source_semantic_value(source, field) != review[field]:
            raise ValueError(f"review/source {field} mismatch for {review['request_id']}")


def build_human_approved(
    review_rows: list[dict[str, Any]],
    sidecar_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Perform the non-normalizing, one-to-one authoritative human join."""
    reviews = review_rows_with_ordinal(review_rows)
    source_by_id = {row["remediation_request_id"]: row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("source remediation manifest has duplicate request IDs")
    review_keys = [(row["request_id"], row["coverage_cell"], row["cell_ordinal"]) for row in reviews]
    sidecar_keys = [
        (row["remediation_request_id"], row["coverage_cell"], row["cell_ordinal"])
        for row in sidecar_rows
    ]
    review_duplicate_count = len(review_keys) - len(set(review_keys))
    sidecar_duplicate_count = len(sidecar_keys) - len(set(sidecar_keys))
    if review_duplicate_count or sidecar_duplicate_count:
        raise ValueError("duplicate G3-B three-part join key")
    sidecar_by_key = {
        (row["remediation_request_id"], row["coverage_cell"], row["cell_ordinal"]): row
        for row in sidecar_rows
    }
    unmatched_reviews = [key for key in review_keys if key not in sidecar_by_key]
    unmatched_sidecars = [key for key in sidecar_keys if key not in set(review_keys)]
    if unmatched_reviews or unmatched_sidecars:
        raise ValueError("G3-B review/human sidecar is not a 1:1 join")
    approved: list[dict[str, Any]] = []
    for review in reviews:
        key = (review["request_id"], review["coverage_cell"], review["cell_ordinal"])
        human = sidecar_by_key[key]
        source_id = review["source_manifest_request_id"]
        try:
            source = source_by_id[source_id]
        except KeyError as exc:
            raise ValueError(f"missing source remediation row: {source_id}") from exc
        assert_review_matches_source(review, source)
        if human.get("authoring_status") != "human_written" or human.get("human_review_status") != "human_approved":
            raise ValueError(f"human sidecar has non-approved row: {review['request_id']}")
        question = human.get("human_final_question")
        if not isinstance(question, str) or not question:
            raise ValueError(f"human sidecar question missing: {review['request_id']}")
        row = deepcopy(source)
        row.update({
            "remediation_request_id": review["request_id"],
            "source_manifest_request_id": source_id,
            "coverage_cell": review["coverage_cell"],
            "cell_ordinal": review["cell_ordinal"],
            "human_final_question": question,
            "final_question": question,
            "authoring_status": "human_written",
            "human_review_status": "human_approved",
            "live_ready_status": "g3b_human_approved_pending_strict_preflight",
            "g3b_status": "human_written_human_approved",
            "g3b_authoritative_review": deepcopy(review),
            "bounded_linguistic_anchor": {
                "anchor_id": f"P49-2H-4D-G3B-HUMAN-{review['request_id'].rsplit('-', 1)[-1]}",
                "anchor_question": question,
                "linguistic_archetype": "G3-B exact human final question; immutable",
                "authoring_status": "human_written",
                "human_review_status": "human_approved",
            },
        })
        approved.append(row)
    result = {
        "review_rows": len(reviews),
        "sidecar_rows": len(sidecar_rows),
        "joined_rows": len(approved),
        "review_duplicate_key_count": review_duplicate_count,
        "sidecar_duplicate_key_count": sidecar_duplicate_count,
        "unmatched_review_rows": len(unmatched_reviews),
        "unmatched_sidecar_rows": len(unmatched_sidecars),
        "join_pass": len(approved) == 27 and not unmatched_reviews and not unmatched_sidecars,
    }
    if not result["join_pass"]:
        raise ValueError("G3-B join did not produce the required 27 rows")
    return approved, result


def revise_failed_human_questions_v2(v1_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create v2 by changing exactly the five user-directed failed questions."""
    if len(v1_rows) != 27:
        raise ValueError("G3-B v2 requires exactly 27 approved v1 rows")
    v1_ids = [row["remediation_request_id"] for row in v1_rows]
    seen = set(v1_ids)
    if len(seen) != len(v1_ids) or not set(HUMAN_REVISIONS_V2) <= seen:
        raise ValueError("G3-B v1 rows do not contain every approved revision ID")
    revised: list[dict[str, Any]] = []
    changed: set[str] = set()
    for source in v1_rows:
        row = deepcopy(source)
        request_id = row["remediation_request_id"]
        if request_id in HUMAN_REVISIONS_V2:
            question = HUMAN_REVISIONS_V2[request_id]
            row["human_final_question"] = question
            row["final_question"] = question
            row["bounded_linguistic_anchor"]["anchor_question"] = question
            row["human_question_revision"] = {
                "revision_version": "v2",
                "revision_scope": "user_directed_editorial_rewrite_after_strict_preflight_failure",
                "prior_human_final_question": source["human_final_question"],
                "authoring_status": "human_written",
                "human_review_status": "human_approved",
            }
            row["live_ready_status"] = "g3b_human_approved_v2_pending_strict_preflight"
            changed.add(request_id)
        revised.append(row)
    if changed != set(HUMAN_REVISIONS_V2):
        raise AssertionError("G3-B v2 did not apply exactly the five approved revisions")
    unchanged = [
        row["remediation_request_id"] for row, source in zip(revised, v1_rows)
        if row["remediation_request_id"] not in HUMAN_REVISIONS_V2
        and row["human_final_question"] != source["human_final_question"]
    ]
    if unchanged:
        raise AssertionError(f"G3-B v2 changed a non-failing human question: {unchanged[0]}")
    return revised


def subject_or_alias_findings(row: dict[str, Any], request: dict[str, Any]) -> list[str]:
    compact = "".join(row["human_final_question"].lower().split())
    host = request["semantic_request"]["host_question_contract"]
    aliases = {"".join(host["subject"].lower().split())}
    aliases.update("".join(value.lower().split()) for value in host.get("request_local_subject_aliases", []))
    return [] if any(alias and alias in compact for alias in aliases) else ["semantic_subject_mismatch"]


def preflight(
    approved_rows: list[dict[str, Any]],
    q1a: dict[str, Any],
    semantic_rows: list[dict[str, Any]],
    pool: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run strict zero-HCX G3-B gates against the immutable 555 baseline."""
    failures: list[dict[str, Any]] = []
    expected_by_cell = q1a_bounded_deficit_by_cell(q1a)
    actual_by_cell = dict(Counter(row["coverage_cell"] for row in approved_rows))
    questions = [row["question"] for row in pool]
    row_checks: list[dict[str, Any]] = []
    for row in approved_rows:
        findings: list[str] = []
        checks = {
            "human_written": row.get("authoring_status") == "human_written" and row.get("bounded_linguistic_anchor", {}).get("authoring_status") == "human_written",
            "human_approved": row.get("human_review_status") == "human_approved" and row.get("bounded_linguistic_anchor", {}).get("human_review_status") == "human_approved",
            "human_final_question_preserved": row.get("final_question") == row.get("human_final_question") == row.get("bounded_linguistic_anchor", {}).get("anchor_question"),
        }
        try:
            adapted = bridge.adapt_remediation_record(row, semantic_rows)
            caller = bridge.caller_input_for(adapted, questions)
            preservation = bridge.preservation_findings(row, adapted)
            diversity = bridge.diversity_prompt_findings(row, caller)
            boundary = bridge.field_boundary_prompt_findings(row, adapted, caller)
            semantic = semantic_question_findings(row["human_final_question"], adapted["semantic_request"])
            subject = subject_or_alias_findings(row, adapted)
            findings.extend(preservation + diversity + boundary + semantic + subject)
            checks.update({
                "bridge_prompt_preservation": not preservation and not diversity and not boundary,
                "semantic_preservation": not semantic and not subject,
                "evidence_preservation": not any("evidence" in item or "source" in item for item in preservation),
                "outcome_preservation": "outcome_mismatch" not in preservation,
                "allowed_fields_preserved": adapted["semantic_request"]["host_question_contract"]["allowed_fields"] == row["semantic_slots"]["allowed_fields"],
                "forbidden_fields_preserved": adapted["semantic_request"]["forbidden_fields"] == row["semantic_slots"]["forbidden_fields"],
                "temporal_scope_preserved": row["semantic_slots"]["temporal_scope"] == "future",
                "target_type_preserved": adapted["semantic_request"]["host_question_contract"]["target_type"] == row["semantic_slots"]["target_type"],
                "unsupported_target_preserved": adapted["semantic_request"]["unsupported_target"] == row["semantic_slots"]["unsupported_target"],
            })
        except (KeyError, ValueError) as exc:
            findings.append(f"preflight_adapter_error:{exc}")
            checks.update({
                "bridge_prompt_preservation": False,
                "semantic_preservation": False,
                "evidence_preservation": False,
                "outcome_preservation": False,
                "allowed_fields_preserved": False,
                "forbidden_fields_preserved": False,
                "temporal_scope_preserved": False,
                "target_type_preserved": False,
                "unsupported_target_preserved": False,
            })
        if not all(checks.values()):
            findings.append("required_preflight_check_failed")
        findings = sorted(set(findings))
        detail = {
            "remediation_request_id": row["remediation_request_id"],
            "coverage_cell": row["coverage_cell"],
            "cell_ordinal": row["cell_ordinal"],
            "human_final_question": row["human_final_question"],
            "checks": checks,
            "findings": findings,
        }
        row_checks.append(detail)
        if findings:
            failures.append(detail)
    provisional = [
        {
            "remediation_request_id": row["remediation_request_id"],
            "validation_status": "pass",
            "generation_status": "not_generated_g3b_preflight",
            "question": row["human_final_question"],
        }
        for row in approved_rows
    ]
    dedup = bridge.full_set_dedup_audit(pool, provisional, bridge.read_jsonl(bridge.FROZEN_SEED))
    dedup_keys = ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    collision_count = sum(len(dedup[key]) for key in dedup_keys)
    report = {
        "stage": "P49-2H-4D-G3-B strict human-approved bounded preflight",
        "external_hcx_calls": 0,
        "authoritative_q1a": str(Q1A),
        "immutable_comparison_pool": str(BASELINE_555),
        "immutable_comparison_pool_sha256": hashlib.sha256(BASELINE_555.read_bytes()).hexdigest(),
        "comparison_pool_pass_count": len(pool),
        "requested": len(approved_rows),
        "requested_by_cell": actual_by_cell,
        "q1a_bounded_deficit_by_cell": expected_by_cell,
        "row_count_pass": len(approved_rows) == 27,
        "q1a_cell_distribution_exact_match": actual_by_cell == expected_by_cell == G3B_EXPECTED_BY_CELL,
        "human_written": sum(item["checks"]["human_written"] for item in row_checks),
        "human_approved": sum(item["checks"]["human_approved"] for item in row_checks),
        "subject_or_allowed_alias_preserved": sum(item["checks"].get("semantic_preservation", False) for item in row_checks),
        "temporal_scope_future_preserved": sum(item["checks"].get("temporal_scope_preserved", False) for item in row_checks),
        "target_type_and_unsupported_target_preserved": sum(item["checks"].get("target_type_preserved", False) and item["checks"].get("unsupported_target_preserved", False) for item in row_checks),
        "allowed_fields_outside_expansion": sum("semantic_forbidden_field_expansion" in item["findings"] for item in row_checks),
        "forbidden_field_expansion": sum("semantic_forbidden_field_expansion" in item["findings"] for item in row_checks),
        "semantic_drift": sum(any(value.startswith(("semantic_", "bounded_")) for value in item["findings"]) for item in row_checks),
        "evidence_drift": sum(not item["checks"].get("evidence_preservation", False) for item in row_checks),
        "outcome_drift": sum(not item["checks"].get("outcome_preservation", False) for item in row_checks),
        "bridge_prompt_preservation_pass": sum(item["checks"].get("bridge_prompt_preservation", False) for item in row_checks),
        "row_checks": row_checks,
        "failures": failures,
        "full_555_set_dedup": dedup,
        "exact_duplicate_count": len(dedup["exact_duplicates"]),
        "normalized_duplicate_count": len(dedup["normalized_duplicates"]),
        "semantic_near_duplicate_count": len(dedup["semantic_near_duplicates"]),
        "frozen_seed_collision_count": len(dedup["frozen_seed_collisions"]),
        "full_set_dedup_pass": collision_count == 0,
    }
    report["preflight_pass"] = (
        report["row_count_pass"]
        and report["q1a_cell_distribution_exact_match"]
        and report["human_written"] == 27
        and report["human_approved"] == 27
        and report["subject_or_allowed_alias_preserved"] == 27
        and report["temporal_scope_future_preserved"] == 27
        and report["target_type_and_unsupported_target_preserved"] == 27
        and report["allowed_fields_outside_expansion"] == 0
        and report["forbidden_field_expansion"] == 0
        and report["semantic_drift"] == 0
        and report["evidence_drift"] == 0
        and report["outcome_drift"] == 0
        and report["bridge_prompt_preservation_pass"] == 27
        and not report["failures"]
        and report["full_set_dedup_pass"]
    )
    report["live_execution_allowed"] = report["preflight_pass"]
    return report


def finding_bucket(finding: str) -> str:
    if finding.startswith(("semantic_", "bounded_")):
        return "semantic_drift"
    if "evidence" in finding:
        return "evidence_drift"
    if "outcome" in finding:
        return "outcome_drift"
    if "subject" in finding or "source" in finding or "provenance" in finding:
        return "subject_provenance_mismatch"
    if "supported" in finding and ("omit" in finding or "missing" in finding):
        return "bounded_supported_part_omission"
    if "forbidden" in finding or "field_boundary" in finding:
        return "forbidden_field_expansion"
    if "duplicate" in finding or "collision" in finding:
        return "near_duplicate_candidate"
    return "new_failure_class"


def quota_credit(
    q1a: dict[str, Any],
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    strict_gate: bool,
) -> dict[str, Any]:
    """Credit only unique Q1A deficit-cell PASS records; never double credit."""
    selected_ids = [row["remediation_request_id"] for row in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("G3-B selected rows contain duplicate identities")
    candidate_ids = [row.get("remediation_request_id") for row in candidates if row.get("validation_status") == "pass"]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("G3-B PASS candidates would double credit an identity")
    unknown = sorted(set(candidate_ids) - set(selected_ids))
    if unknown:
        raise ValueError(f"G3-B PASS candidate is outside selected tranche: {unknown[0]}")
    deficits = q1a_bounded_deficit_by_cell(q1a)
    raw_pass_by_cell = Counter(
        row["coverage_cell"] for row in candidates
        if row.get("validation_status") == "pass" and row.get("remediation_request_id") in set(selected_ids)
    )
    credit_by_cell = {cell: min(raw_pass_by_cell[cell], deficit) for cell, deficit in deficits.items()}
    total_credit = sum(credit_by_cell.values())
    if total_credit > 27 or any(credit_by_cell[cell] > deficits[cell] for cell in credit_by_cell):
        raise AssertionError("G3-B quota credit exceeded Q1A residual")
    return {
        "strict_tranche_gate_closed": strict_gate,
        "total_quota_credit_before": TOTAL_CREDIT_BEFORE,
        "bounded_credit_before": BOUNDED_CREDIT_BEFORE,
        "pass_by_cell": dict(raw_pass_by_cell),
        "credit_by_cell": credit_by_cell,
        "actual_bounded_credit": total_credit,
        "bounded_credit_after": BOUNDED_CREDIT_BEFORE + total_credit,
        "total_quota_credit_after": TOTAL_CREDIT_BEFORE + total_credit,
        "bounded_target": BOUNDED_TARGET,
        "total_target": TOTAL_TARGET,
        "bounded_surplus_credit": max(0, BOUNDED_CREDIT_BEFORE + total_credit - BOUNDED_TARGET),
        "total_surplus_credit": max(0, TOTAL_CREDIT_BEFORE + total_credit - TOTAL_TARGET),
        "all_27_quota_eligible_pass": strict_gate and total_credit == 27,
    }


def live_audit(
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    pool: list[dict[str, Any]],
    q1a: dict[str, Any],
) -> dict[str, Any]:
    findings = Counter(finding for trace in traces for finding in trace.get("validation_findings", []))
    buckets = Counter()
    for finding, count in findings.items():
        buckets[finding_bucket(finding)] += count
    full_dedup = bridge.full_set_dedup_audit(pool, candidates, bridge.read_jsonl(bridge.FROZEN_SEED))
    dedup_collisions = sum(len(full_dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    passed = [candidate for candidate in candidates if candidate.get("validation_status") == "pass"]
    final_question_preserved = all(
        candidate.get("question") == next(
            row["human_final_question"] for row in selected
            if row["remediation_request_id"] == candidate.get("remediation_request_id")
        )
        and candidate.get("model_question_raw")
        for candidate in candidates
    )
    bridge_healthy = len(traces) == len(selected) and all(
        trace["caller_input_preservation_pass"]
        and trace["diversity_control_prompt_pass"]
        and trace["field_boundary_prompt_pass"]
        and trace["external_call_success"]
        and trace["response_schema_valid"]
        and trace["build_full_candidate_status"] == "success"
        and trace["hydration_status"] == "success"
        and trace["validator_executed"]
        for trace in traces
    )
    strict_gate = (
        len(passed) == len(selected) == 27
        and not findings
        and not buckets["new_failure_class"]
        and dedup_collisions == 0
        and bridge_healthy
        and final_question_preserved
        and not any(trace["generation_status"] == "generation_exhausted" for trace in traces)
    )
    quota = quota_credit(q1a, selected, candidates, strict_gate=strict_gate)
    return {
        "stage": "P49-2H-4D-G3-B bounded human-approved live tranche",
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "logical_requests": len(selected),
        "comparison_pool_before": len(pool),
        "candidate_question_authority": "host_owned_human_final_question",
        "hcx_model_question_authority": "audit_only",
        "generated_records": sum(trace["external_call_success"] for trace in traces),
        "pass": len(passed),
        "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        "bridge_healthy": bridge_healthy,
        "human_final_question_preserved": final_question_preserved,
        "strict_findings": {
            "semantic_drift": buckets["semantic_drift"],
            "evidence_drift": buckets["evidence_drift"],
            "outcome_drift": buckets["outcome_drift"],
            "subject_provenance_mismatch": buckets["subject_provenance_mismatch"],
            "bounded_supported_part_omission": buckets["bounded_supported_part_omission"],
            "forbidden_field_expansion": buckets["forbidden_field_expansion"],
            "near_duplicate_candidate": buckets["near_duplicate_candidate"],
            "new_failure_class": buckets["new_failure_class"],
            "generation_exhausted": sum(trace["generation_status"] == "generation_exhausted" for trace in traces),
        },
        "validation_findings": dict(sorted(findings.items())),
        "new_failure_classes": sorted(
            finding for finding in findings if finding_bucket(finding) == "new_failure_class"
        ),
        "full_582_set_dedup": full_dedup,
        "full_set_dedup_pass": dedup_collisions == 0,
        "strict_tranche_quality_go": strict_gate,
        "quota_credit": quota,
        "promotion_allowed": strict_gate and quota["all_27_quota_eligible_pass"],
        "batch_08_original_manifest_allowed": False,
        "h_live_allowed": False,
        "i_live_allowed": False,
    }


def promote(
    pool: list[dict[str, Any]], candidates: list[dict[str, Any]], audit: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not audit.get("promotion_allowed") or not audit["quota_credit"].get("all_27_quota_eligible_pass"):
        raise ValueError("G3-B strict tranche gate is not closed")
    passes = [deepcopy(row) for row in candidates if row.get("validation_status") == "pass"]
    if len(passes) != 27:
        raise ValueError("G3-B promotion requires exactly 27 PASS candidates")
    baseline_ids = {row.get("remediation_request_id") or row.get("candidate_id") for row in pool}
    pass_ids = [row["remediation_request_id"] for row in passes]
    if len(pass_ids) != len(set(pass_ids)) or baseline_ids & set(pass_ids):
        raise ValueError("G3-B promotion identity overlap would double credit")
    for row in passes:
        row.update({
            "quality_pool_promotion_status": "promoted_validation_pass",
            "quality_pool_promotion_scope": "additive_comparison_pool_only",
            "quality_pool_promotion_is_acceptance": False,
            "g3b_quota_credit_status": "credited_q1a_bounded_deficit",
        })
    promoted_pool = [*pool, *passes]
    dedup = bridge.full_set_dedup_audit(promoted_pool, [], bridge.read_jsonl(bridge.FROZEN_SEED))
    collisions = sum(len(dedup[key]) for key in (
        "exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions",
    ))
    if collisions:
        raise ValueError("G3-B promotion pool failed immutable full-set dedup")
    promotion_audit = {
        "stage": "P49-2H-4D-G3-B strict bounded promotion / 582 comparison pool",
        "external_hcx_calls": 0,
        "prior_comparison_pool": str(BASELINE_555),
        "prior_comparison_pool_sha256": hashlib.sha256(BASELINE_555.read_bytes()).hexdigest(),
        "prior_comparison_pool_count": len(pool),
        "prior_comparison_pool_modified": False,
        "promoted_count": len(passes),
        "new_comparison_pool_count": len(promoted_pool),
        "promotion_candidate_ids": pass_ids,
        "full_582_set_dedup": dedup,
        "full_582_set_dedup_pass": True,
        "quota_credit": audit["quota_credit"],
        "strict_tranche_gate_closed": True,
        "batch_08_original_manifest_allowed": False,
    }
    return passes, promoted_pool, promotion_audit


def prepare_residual_lane(q1a: dict[str, Any], lane: str, expected_deficit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    residuals = q1a_residuals(q1a, lane)
    total = sum(row["deficit"] for row in residuals)
    rows: list[dict[str, Any]] = []
    for ordinal, original in enumerate(sorted(residuals, key=lambda row: row["coverage_cell"]), start=1):
        row = deepcopy(original)
        row.update({
            "preparation_request_id": f"P49-2H-4D-{'H' if lane == 'clarification_required' else 'I'}-{ordinal:03d}",
            "preparation_lane": lane,
            "q1a_authority": str(Q1A),
            "live_execution_allowed": False,
            "external_hcx_calls": 0,
            "preparation_status": "residual_manifest_only_no_hcx",
        })
        rows.append(row)
    report = {
        "stage": f"P49-2H-4D {'H clarification' if lane == 'clarification_required' else 'I supported'} residual preflight",
        "external_hcx_calls": 0,
        "q1a_authority": str(Q1A),
        "lane": lane,
        "cell_count": len(rows),
        "cell_target_total": sum(row["allocation_target"] for row in rows),
        "cell_current_total": sum(row["current_unique_555"] for row in rows),
        "cell_credited_total": sum(row["credited"] for row in rows),
        "cell_deficit_total": total,
        "expected_deficit": expected_deficit,
        "cell_rows": [
            {
                key: row[key]
                for key in ("coverage_cell", "allocation_target", "current_unique_555", "credited", "deficit")
            }
            for row in rows
        ],
        "exact_residual_manifest_pass": total == expected_deficit and all(row["deficit"] > 0 for row in rows),
        "live_execution_allowed": False,
        "live_execution_block_reason": "G3-B preparation-only scope: HCX live calls are explicitly prohibited for H/I",
    }
    return rows, report


def prepare_artifacts() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Create the join and strict preflight artifacts, with zero HCX calls."""
    approved, join = build_human_approved(
        bridge.read_jsonl(REVIEW_MANIFEST), bridge.read_jsonl(HUMAN_SIDECAR), bridge.read_jsonl(SOURCE_MANIFEST),
    )
    q1a = read_json(Q1A)
    pool = [row for row in bridge.read_jsonl(BASELINE_555) if row.get("validation_status") == "pass"]
    if len(pool) != 555:
        raise ValueError(f"authoritative comparison pool must contain 555 PASS rows; found {len(pool)}")
    report = preflight(approved, q1a, bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
    report["join"] = join
    write_new_jsonl(APPROVED, approved)
    write_new_json(PREFLIGHT, report)
    return approved, report


def run_live(
    approved: list[dict[str, Any]],
    preflight_report: dict[str, Any],
    *,
    trace_output: Path = TRACE,
    candidate_output: Path = CANDIDATES,
    audit_output: Path = AUDIT,
    promotion_output: Path = PROMOTION,
    promotion_audit_output: Path = PROMOTION_AUDIT,
    promoted_pool_output: Path = PROMOTED_POOL,
) -> dict[str, Any]:
    if not preflight_report.get("preflight_pass"):
        raise ValueError("G3-B strict preflight failed; HCX invocation is prohibited")
    for path in (trace_output, candidate_output, audit_output, promotion_output, promotion_audit_output, promoted_pool_output):
        if path.exists():
            raise FileExistsError(f"refusing G3-B live because artifact already exists: {path}")
    q1a = read_json(Q1A)
    pool = [row for row in bridge.read_jsonl(BASELINE_555) if row.get("validation_status") == "pass"]
    if len(pool) != 555:
        raise ValueError("immutable comparison baseline is not the authoritative 555 PASS pool")
    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    semantic_rows = bridge.read_jsonl(bridge.SEMANTIC_REQUESTS)
    comparison_questions = [row["question"] for row in pool]
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for row in approved:
        adapted = bridge.adapt_remediation_record(row, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            row, adapted, mode="g3b-human-tranche", generator=generator, corpus=corpus,
            seed_questions=seed_questions, comparison_questions=comparison_questions, max_generation_attempts=3,
        )
        trace.update({
            "cell_ordinal": row["cell_ordinal"],
            "human_final_question": row["human_final_question"],
            "candidate_question_authority": "host_owned_human_final_question",
            "hcx_model_question_authority": "audit_only",
        })
        if candidate is not None:
            candidate.update({
                "human_final_question": row["human_final_question"],
                "final_question": row["human_final_question"],
                "candidate_question_authority": "host_owned_human_final_question",
                "hcx_model_question_authority": "audit_only",
            })
            trace["human_final_question_preserved"] = candidate.get("question") == row["human_final_question"]
            candidates.append(candidate)
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])
        else:
            trace["human_final_question_preserved"] = False
        traces.append(trace)
        bridge.append_jsonl(trace_output, [trace])
        if candidate is not None:
            bridge.append_jsonl(candidate_output, [candidate])
    report = live_audit(approved, traces, candidates, pool, q1a)
    write_new_json(audit_output, report)
    if report["promotion_allowed"]:
        promoted, promoted_pool, promotion_audit = promote(pool, candidates, report)
        write_new_jsonl(promotion_output, promoted)
        write_new_jsonl(promoted_pool_output, promoted_pool)
        write_new_json(promotion_audit_output, promotion_audit)
    return report


def prepare_h_i() -> dict[str, Any]:
    q1a = read_json(Q1A)
    h_rows, h_report = prepare_residual_lane(q1a, "clarification_required", 26)
    i_rows, i_report = prepare_residual_lane(q1a, "supported_answer", 48)
    write_new_jsonl(H_MANIFEST, h_rows)
    write_new_json(H_PREFLIGHT, h_report)
    write_new_jsonl(I_MANIFEST, i_rows)
    write_new_json(I_PREFLIGHT, i_report)
    return {"h": h_report, "i": i_report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run exactly the preflighted 27 logical G3-B HCX requests.")
    parser.add_argument("--prepare-v2", action="store_true", help="Create v2 by revising exactly the five user-directed human questions, with zero HCX calls.")
    parser.add_argument("--live-v2", action="store_true", help="Run exactly the preflighted 27 logical G3-B v2 HCX requests.")
    parser.add_argument("--prepare-hi", action="store_true", help="Create only H/I residual manifests and zero-HCX preflights.")
    args = parser.parse_args()
    if sum((args.live, args.prepare_v2, args.live_v2, args.prepare_hi)) > 1:
        parser.error("choose only one execution mode")
    if args.prepare_hi:
        reports = prepare_h_i()
        print(json.dumps({
            "h_deficit": reports["h"]["cell_deficit_total"], "h_hcx_calls": 0,
            "i_deficit": reports["i"]["cell_deficit_total"], "i_hcx_calls": 0,
        }, ensure_ascii=False))
        return
    if args.prepare_v2:
        if not APPROVED.exists():
            parser.error("the immutable v1 human-approved artifact is required before creating v2")
        v2_rows = revise_failed_human_questions_v2(bridge.read_jsonl(APPROVED))
        pool = [row for row in bridge.read_jsonl(BASELINE_555) if row.get("validation_status") == "pass"]
        report = preflight(v2_rows, read_json(Q1A), bridge.read_jsonl(bridge.SEMANTIC_REQUESTS), pool)
        report["v2_revision"] = {
            "changed_request_ids": sorted(HUMAN_REVISIONS_V2),
            "unchanged_human_question_count": 22,
            "validator_changed": False,
            "dedup_threshold_changed": False,
            "semantic_contract_changed": False,
        }
        write_new_jsonl(V2_APPROVED, v2_rows)
        write_new_json(V2_PREFLIGHT, report)
        print(json.dumps({
            "external_hcx_calls": 0, "revised_rows": len(HUMAN_REVISIONS_V2), "unchanged_rows": 22,
            "preflight_pass": report["preflight_pass"], "requested": len(v2_rows),
        }, ensure_ascii=False))
        return
    if not args.live and not args.live_v2:
        approved, report = prepare_artifacts()
        print(json.dumps({
            "external_hcx_calls": 0, "join": report["join"], "preflight_pass": report["preflight_pass"],
            "requested": len(approved), "preflight_output": str(PREFLIGHT),
        }, ensure_ascii=False))
        return
    approved_path = V2_APPROVED if args.live_v2 else APPROVED
    if not approved_path.exists():
        parser.error("run the required zero-HCX G3-B join/preflight first")
    approved = bridge.read_jsonl(approved_path)
    current = preflight(
        approved, read_json(Q1A), bridge.read_jsonl(bridge.SEMANTIC_REQUESTS),
        [row for row in bridge.read_jsonl(BASELINE_555) if row.get("validation_status") == "pass"],
    )
    if not current["preflight_pass"]:
        parser.error("G3-B strict preflight failed; no HCX call was made")
    report = run_live(
        approved, current,
        trace_output=V2_TRACE if args.live_v2 else TRACE,
        candidate_output=V2_CANDIDATES if args.live_v2 else CANDIDATES,
        audit_output=V2_AUDIT if args.live_v2 else AUDIT,
        promotion_output=V2_PROMOTION if args.live_v2 else PROMOTION,
        promotion_audit_output=V2_PROMOTION_AUDIT if args.live_v2 else PROMOTION_AUDIT,
        promoted_pool_output=V2_PROMOTED_POOL if args.live_v2 else PROMOTED_POOL,
    )
    print(json.dumps({
        key: report[key] for key in (
            "external_hcx_calls", "logical_requests", "pass", "generation_exhausted",
            "strict_tranche_quality_go", "promotion_allowed",
        )
    } | {"quota_credit": report["quota_credit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
