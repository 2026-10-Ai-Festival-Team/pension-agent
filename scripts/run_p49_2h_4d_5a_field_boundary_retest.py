"""P49-2H-4D-5A: guarded same-record field-boundary retest.

This runner is deliberately limited to the two Batch-05 records that exposed
``semantic_forbidden_field_expansion`` and two still-unattempted neighbours of
the same canonical requirement.  It reuses the established 4C bridge,
canonical v4 candidate builder, hydration, and validator; it contains no new
generation, validation, or dedup policy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_p49_2h_4c_execution_bridge as bridge


FAILED_RETEST_IDS = ("P49-2H-4B-0158", "P49-2H-4B-0159")
NEIGHBOR_SMOKE_IDS = ("P49-2H-4B-0207", "P49-2H-4B-0208")
DEFAULT_BASELINE_CANDIDATES = (
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_smoke_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4c_3_retry_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_01_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_02_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_03_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_04_candidates_v1.jsonl",
    ROOT / "evaluation/fine_tuning/p49_2h_4d_batch_05_candidates_v1.jsonl",
)
DEFAULT_ATTEMPTED_TRACES = tuple(
    ROOT / f"evaluation/fine_tuning/p49_2h_4d_batch_{number:02d}_trace_v1.jsonl"
    for number in range(1, 6)
)


def read_many(paths: list[Path] | tuple[Path, ...]) -> list[dict[str, Any]]:
    return [row for path in paths for row in bridge.read_jsonl(path)]


def select_phase_records(
    manifest_rows: list[dict[str, Any]],
    *,
    phase: str,
    attempted_ids: set[str],
) -> list[dict[str, Any]]:
    """Select only the frozen same-record retest or its unattempted neighbours."""
    ids = FAILED_RETEST_IDS if phase == "same-record-retest" else NEIGHBOR_SMOKE_IDS
    by_id = {row["remediation_request_id"]: row for row in manifest_rows}
    if any(request_id not in by_id for request_id in ids):
        raise ValueError("5A selection is incomplete in the immutable remediation manifest")
    selected = [by_id[request_id] for request_id in ids]
    if phase == "same-record-retest":
        if not set(ids) <= attempted_ids:
            raise ValueError("same-record retest IDs must be the two already-attempted Batch-05 failures")
    else:
        if set(ids) & attempted_ids:
            raise ValueError("neighbor mini-smoke IDs must remain unattempted before this phase")
        if not all(
            row["target_outcome"] == "supported_answer"
            and row["canonical_requirement"] == "pension_savings.tax_credit.limit"
            for row in selected
        ):
            raise ValueError("neighbor mini-smoke must remain on the D09 tax-limit supported requirement")
    return selected


def preflight(
    selected: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the same bridge with zero external calls and expose field binding."""
    traces: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    for remediation in selected:
        request = bridge.adapt_remediation_record(remediation, semantic_rows)
        trace, candidate = bridge.execute_adapted_request(
            remediation,
            request,
            mode="dry-run",
            comparison_questions=[],
        )
        if candidate is not None:
            raise AssertionError("dry-run must not produce a candidate")
        traces.append(trace)
        requests.append(request)
    return traces, requests


def phase_audit(
    *,
    phase: str,
    selected: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    baseline_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    immutable_pass = [
        row
        for row in bridge.read_jsonl(bridge.COMPARISON_POOL)
        if row.get("validation_status") == "pass"
    ]
    all_audited_candidates = [*baseline_candidates, *candidates]
    dedup = bridge.full_set_dedup_audit(
        immutable_pass,
        all_audited_candidates,
        bridge.read_jsonl(bridge.FROZEN_SEED),
    )
    by_id = {candidate["remediation_request_id"]: candidate for candidate in candidates}
    if len(selected) != len(traces):
        raise AssertionError("5A selected records and traces must align")
    results = []
    for remediation, trace in zip(selected, traces):
        candidate = by_id.get(remediation["remediation_request_id"])
        results.append(
            {
                "remediation_request_id": remediation["remediation_request_id"],
                "coverage_cell": remediation["coverage_cell"],
                "external_calls": trace["attempt_count"],
                "bridge_pass": (
                    trace["caller_input_preservation_pass"]
                    and trace["response_schema_valid"] is True
                    and trace["build_full_candidate_status"] == "success"
                    and trace["hydration_status"] == "success"
                    and trace["validator_executed"]
                ),
                "field_boundary_prompt_pass": trace["field_boundary_prompt_pass"],
                "validation_status": trace["validation_status"],
                "validation_findings": trace["validation_findings"],
                "semantic_forbidden_field_expansion": "semantic_forbidden_field_expansion" in trace["validation_findings"],
                "subject_provenance_mismatch": "subject_provenance_mismatch" in trace["validation_findings"],
                "near_duplicate": any(finding.startswith("near_duplicate") for finding in trace["validation_findings"]),
                "generation_status": trace["generation_status"],
                "candidate_promoted": candidate is not None and candidate.get("validation_status") == "pass",
            }
        )
    clean_dedup = not any(
        dedup[key]
        for key in ("exact_duplicates", "normalized_duplicates", "semantic_near_duplicates", "frozen_seed_collisions")
    )
    return {
        "stage": "P49-2H-4D-5A semantic_forbidden_field_expansion retest",
        "phase": phase,
        "requested": len(selected),
        "external_hcx_calls": sum(trace["attempt_count"] for trace in traces),
        "field_boundary_instruction_present": sum(trace["field_boundary_prompt_pass"] for trace in traces),
        "semantic_control_preservation_pass": sum(trace["caller_input_preservation_pass"] for trace in traces),
        "field_boundary_contract_failures": [
            trace["remediation_request_id"]
            for trace in traces
            if trace["field_boundary_prompt_findings"]
        ],
        "results": results,
        "full_comparison_dedup": dedup,
        "dedup_pass": clean_dedup,
        "phase_pass": len(results) == len(selected) and all(
            result["bridge_pass"]
            and result["field_boundary_prompt_pass"]
            and result["candidate_promoted"]
            and not result["semantic_forbidden_field_expansion"]
            and not result["subject_provenance_mismatch"]
            and not result["near_duplicate"]
            for result in results
        ) and clean_dedup,
        "acceptance_allowed": False,
        "training_export_allowed": False,
        "tuning_allowed": False,
    }


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite 5A audit artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("same-record-retest", "neighbor-mini-smoke"), default="same-record-retest")
    parser.add_argument("--live", action="store_true", help="Allow only the frozen two-record phase to call HCX-007.")
    parser.add_argument("--manifest", type=Path, default=bridge.REMEDIATION_MANIFEST)
    parser.add_argument("--semantic-requests", type=Path, default=bridge.SEMANTIC_REQUESTS)
    parser.add_argument("--baseline-candidates", type=Path, action="append")
    parser.add_argument("--attempted-trace", type=Path, action="append")
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.max_generation_attempts <= 3:
        parser.error("--max-generation-attempts must be within 1..3")

    manifest_rows = bridge.read_jsonl(args.manifest)
    semantic_rows = bridge.read_jsonl(args.semantic_requests)
    baseline_paths = args.baseline_candidates or list(DEFAULT_BASELINE_CANDIDATES)
    attempted_paths = args.attempted_trace or list(DEFAULT_ATTEMPTED_TRACES)
    attempted_ids = {row["remediation_request_id"] for row in read_many(attempted_paths)}
    selected = select_phase_records(manifest_rows, phase=args.phase, attempted_ids=attempted_ids)
    dry_traces, requests = preflight(selected, semantic_rows)
    if not args.live:
        audit = phase_audit(
            phase=args.phase,
            selected=selected,
            traces=dry_traces,
            candidates=[],
            baseline_candidates=read_many(baseline_paths),
        )
        audit["external_hcx_calls"] = 0
        audit["phase_pass"] = all(
            trace["caller_input_preservation_pass"]
            and trace["field_boundary_prompt_pass"]
            for trace in dry_traces
        )
        write_new_json(args.audit_output, audit)
        print(json.dumps({"phase": args.phase, "requested": len(selected), "external_hcx_calls": 0, "phase_pass": audit["phase_pass"], "audit_output": str(args.audit_output)}, ensure_ascii=False))
        return
    if any(
        not trace["caller_input_preservation_pass"] or not trace["field_boundary_prompt_pass"]
        for trace in dry_traces
    ):
        parser.error("5A preflight failed; no HCX call was made")
    for path in (args.trace_output, args.candidate_output, args.audit_output):
        if path.exists():
            parser.error(f"5A live artifact already exists; choose a new path: {path}")

    generator = bridge.configured_generator()
    corpus = {row["chunk_id"]: row for row in bridge.read_jsonl(bridge.CORPUS)}
    seed_questions = [row["question"] for row in bridge.read_jsonl(bridge.FROZEN_SEED)]
    baseline_candidates = read_many(baseline_paths)
    comparison_questions = bridge.validated_questions([
        *bridge.read_jsonl(bridge.COMPARISON_POOL),
        *baseline_candidates,
    ])
    traces: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    if len(selected) != len(requests):
        raise AssertionError("5A selected records and adapted requests must align")
    for remediation, request in zip(selected, requests):
        trace, candidate = bridge.execute_adapted_request(
            remediation,
            request,
            mode="single-live",
            generator=generator,
            corpus=corpus,
            seed_questions=seed_questions,
            comparison_questions=comparison_questions,
            max_generation_attempts=args.max_generation_attempts,
        )
        trace["phase"] = args.phase
        traces.append(trace)
        bridge.append_jsonl(args.trace_output, [trace])
        if candidate is not None:
            candidate["phase"] = args.phase
            candidates.append(candidate)
            bridge.append_jsonl(args.candidate_output, [candidate])
            if candidate.get("validation_status") == "pass":
                comparison_questions.append(candidate["question"])
    audit = phase_audit(
        phase=args.phase,
        selected=selected,
        traces=traces,
        candidates=candidates,
        baseline_candidates=baseline_candidates,
    )
    write_new_json(args.audit_output, audit)
    print(json.dumps({"phase": args.phase, "requested": len(selected), "external_hcx_calls": audit["external_hcx_calls"], "phase_pass": audit["phase_pass"], "audit_output": str(args.audit_output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
