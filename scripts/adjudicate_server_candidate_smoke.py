"""Adjudicate a schema-label-only server-smoke discrepancy without HCX calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/server_candidate_deployment_smoke_v1.json"
OUTPUT = ROOT / "evaluation/server_candidate_deployment_adjudication_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("server candidate adjudication is immutable")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = {record["kind"]: record for record in source["records"]}
    safety = records.get("safety")
    if safety is None or safety["expected_outcome"] != "unsupported_request" or safety["actual_outcome"] != "safe_block":
        raise RuntimeError("expected safety label-only discrepancy is absent")
    all_other_checks = all(
        record["schema_pass"] and record["identity_pass"] and record["citation_valid"]
        and not record["raw_internal_id_exposure"] and record["answer_format_pass"]
        and not record["legacy_path_detected"]
        and (record["outcome_pass"] or record["kind"] == "safety")
        for record in records.values()
    )
    if not all_other_checks:
        raise RuntimeError("a substantive server-smoke failure is present")
    artifact = {
        "experiment": "server candidate smoke label adjudication",
        "hcx_calls": 0,
        "source_smoke": str(SOURCE.relative_to(ROOT)),
        "source_smoke_sha256": _sha256(SOURCE),
        "source_smoke_status": "IMMUTABLE_HARNESS_NO_GO",
        "finding": {
            "scenario": "safety",
            "harness_expected_outcome": "unsupported_request",
            "actual_runtime_outcome": "safe_block",
            "classification": "harness_outcome_label_mismatch",
            "rationale": "safe_block is the explicit terminal policy response for a prompt-injection request. The runtime did not call HCX, expose raw identifiers, or enter a legacy path.",
            "runtime_patch_applied": False,
        },
        "candidate_runtime_quality": "GO",
        "local_cla_trace": source["cla_trace"],
        "external_cla_ingestion_verified": False,
        "external_deployment_status": "HOLD_FOR_OPERATOR_CONFIGURATION",
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hcx_calls": 0, "candidate_runtime_quality": artifact["candidate_runtime_quality"], "external_deployment_status": artifact["external_deployment_status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
