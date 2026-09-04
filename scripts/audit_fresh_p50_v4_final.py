"""Finalize the immutable Fresh P50 v4 audit without any HCX calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v4.jsonl"
METADATA = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v4_metadata.json"
PREFLIGHT = ROOT / "evaluation/fresh_p50_v4_static_preflight_v4.json"
EXECUTION = ROOT / "evaluation/fresh_p50_final_holdout_execution_v4.json"
OUTPUT = ROOT / "evaluation/fresh_p50_v4_final_audit_v1.json"


def _sha_rows(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("v4 final audit is immutable")
    rows = [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    outputs = execution["outputs"]
    if len(rows) != 50 or len(outputs) != 50:
        raise RuntimeError("v4 record count is incomplete")
    if metadata["manifest_sha256"] != _sha_rows(rows) or preflight["decision"] != "PASS":
        raise RuntimeError("v4 holdout authority is not frozen/preflight PASS")
    failed = [
        {"id": output["id"], "question": output["question"], "failure_classes": output["failure_classes"], "actual_outcome": output["actual_outcome"], "expected_outcome": output["expected_outcome"]}
        for output in outputs if not output["strict_pass"]
    ]
    axes = {
        axis: sum(bool(output.get("evaluation_axes", {}).get(axis)) for output in outputs)
        for axis in ("correctness", "evidence_completeness", "requirement_coverage", "grounding_hallucination", "reasoning_consistency", "safety_reliability", "information_limit_handling", "citation_document_display")
    }
    supported = [output for output in outputs if output["expected_outcome"] == "supported_answer"]
    style = {
        "supported_count": len(supported),
        "direct_answer_present": sum(output["style_audit"]["direct_answer_present"] for output in supported),
        "explanation_present": sum(output["style_audit"]["explanation_present"] for output in supported),
        "semantic_explanation": sum(output["style_audit"]["semantic_explanation"] for output in supported),
        "repetitive_content": sum(output["style_audit"]["repetitive_content"] for output in supported),
    }
    artifact = {
        "experiment": "Fresh P50 v4 final audit",
        "decision": "IMMUTABLE_NO_GO",
        "hcx_calls": 0,
        "authority": {
            "holdout": str(HOLDOUT.relative_to(ROOT)), "manifest_sha256": metadata["manifest_sha256"],
            "prompt_id": metadata["prompt_id"], "prompt_sha256": metadata["prompt_sha256"],
            "preflight": str(PREFLIGHT.relative_to(ROOT)), "preflight_sha256": _sha_file(PREFLIGHT),
            "execution": str(EXECUTION.relative_to(ROOT)), "execution_sha256": _sha_file(EXECUTION),
        },
        "execution_summary": execution["summary"],
        "competition_axes_pass_count": axes,
        "supported_style_audit": style,
        "failure_rows": failed,
        "server_candidate_deployment": "HOLD",
        "prohibited_after_no_go": ["automatic_patch", "failed-row_rerun", "v4_rerun", "v5_holdout_generation", "server_deployment"],
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": artifact["decision"], "pass_count": execution["summary"]["pass_count"], "critical_failure_count": execution["summary"]["critical_failure_count"], "output": str(OUTPUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
