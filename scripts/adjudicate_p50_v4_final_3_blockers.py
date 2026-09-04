"""Adjudicate the final v4 regression blockers without an HCX call."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "evaluation/fresh_p50_v2_regression_execution_v7.json"
CHUNKS = ROOT / "data/parsed/chunks.jsonl"
OUTPUT = ROOT / "evaluation/p50_v4_final_3_blocker_adjudication_v1.json"
TARGET_IDS = {"P50V4-020", "P50V4-031", "P50V4-033"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise RuntimeError("final-3 adjudication is immutable")
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    outputs = {row["id"]: row for row in execution["outputs"]}
    if not TARGET_IDS <= outputs.keys():
        raise RuntimeError("v7 execution does not contain every final blocker")

    selected_ids = set(outputs["P50V4-020"]["cited_chunk_ids"])
    selected_chunks = []
    for line in CHUNKS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("chunk_id") in selected_ids:
            selected_chunks.append({
                "chunk_id": row["chunk_id"],
                "source_path": row["source_path"],
                "text": row.get("text", ""),
            })
    source_path = ROOT / "data/raw/연금/docs_renamed/doc36.docx"
    evidence_anchor = "연금수령 시 연금소득으로 분리과세"
    if not any(evidence_anchor in row["text"] for row in selected_chunks):
        raise RuntimeError("selected primary evidence does not support the non-exemption adjudication")

    artifact = {
        "experiment": "P50 v4 final 3-blocker HCX-0 root-cause adjudication",
        "hcx_calls": 0,
        "source_execution": str(EXECUTION.relative_to(ROOT)),
        "original_v4_status": "IMMUTABLE_NO_GO",
        "rows": [
            {
                "record_id": "P50V4-020",
                "benchmark_valid": True,
                "canonical_requirements": outputs["P50V4-020"]["actual_requirements"],
                "required_facts": outputs["P50V4-020"]["required_facts"],
                "selected_primary_evidence": selected_chunks,
                "authoritative_source_path": "data/raw/연금/docs_renamed/doc36.docx",
                "authoritative_source_sha256": _sha256(source_path),
                "answer_fact_expression": "비과세가 아니라",
                "classification": "canonical_fact_lexical_equivalence_defect",
                "root_cause": "The selected original-primary evidence and the answer both preserve non-exemption; the scorer only looked for the canonical surface `면세` and did not recognise the negation-preserving equivalent `비과세가 아니라`.",
                "permitted_change": "Restrict the scorer to the exact canonical equivalence 면세 ↔ 비과세; no host completion, evidence binding, prompt, or threshold change.",
                "runtime_patch_applied": False,
            },
            {
                "record_id": "P50V4-031",
                "benchmark_valid": True,
                "expected_canonical_requirements": [],
                "taxonomy_audit": "No requirement is expected because this must terminate as a future-evidence-limit bounded answer before selection.",
                "classification": "future_boundary_natural_language_normalization",
                "root_cause": "`위험 분류` was not included in the bounded-policy field aliases for the canonical risk-grade concept.",
                "permitted_change": "Add the generic field alias 위험분류 to the terminal future-boundary policy; no selector fallback or question-specific mapping.",
            },
            {
                "record_id": "P50V4-033",
                "benchmark_valid": True,
                "expected_canonical_requirements": [],
                "taxonomy_audit": "ISA.transfer.additional_tax_credit exists and was selected in v7, but this must terminate as a future-evidence-limit bounded answer before selection.",
                "classification": "future_boundary_natural_language_normalization",
                "root_cause": "The future-boundary concrete-value markers recognised `같을지` and `같을까`, but not the natural guarantee construction `같다고 보장`.",
                "permitted_change": "Add the generic persistence marker 같다고 to the terminal future-boundary policy; no selector fallback or question-specific mapping.",
            },
        ],
        "decision": "MINIMAL_NORMALIZATION_REPAIR_AUTHORIZED",
        "prohibited": ["v4 manifest mutation", "exact-question hardcoding", "broad selector fallback", "threshold relaxation", "prompt/model change"],
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hcx_calls": 0, "decision": artifact["decision"], "rows": len(artifact["rows"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
