"""Adjudicate P50V3-006 without an HCX call.

This records whether the frozen required fact ``증빙서류`` is an actual
selected-evidence document requirement or merely an over-specific benchmark
wording.  It deliberately reads immutable artifacts only and never changes
the holdout, prompt, or validator.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3.jsonl"
EXECUTION = ROOT / "evaluation/fresh_p50_v2_regression_execution_v5.json"
CHUNKS = ROOT / "data/parsed/chunks.jsonl"
RAW_SOURCE = ROOT / "data/raw/연금/docs_renamed/doc46.pdf"
OUTPUT = ROOT / "evaluation/p50v3_006_required_fact_adjudication_v1.json"
RECORD_ID = "P50V3-006"
SELECTED_CHUNK_IDS = (
    "04782a392f49293e-paragraph_group-4390ad8476e5",
    "15fb5460a23aa10d-paragraph_group-9b55ec13ba82",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl_record(path: Path, record_id: str) -> dict:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and (record := json.loads(line)).get("id") == record_id:
            return record
    raise RuntimeError(f"missing {record_id} in {path}")


def _load_execution_record(path: Path, record_id: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload.get("results", payload.get("outputs", [])):
        if record.get("id") == record_id:
            return record
    raise RuntimeError(f"missing {record_id} in {path}")


def main() -> None:
    holdout = _load_jsonl_record(HOLDOUT, RECORD_ID)
    execution = _load_execution_record(EXECUTION, RECORD_ID)
    parsed_chunks = {
        chunk["chunk_id"]: chunk
        for line in CHUNKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for chunk in (json.loads(line),)
        if chunk["chunk_id"] in SELECTED_CHUNK_IDS
    }
    if set(parsed_chunks) != set(SELECTED_CHUNK_IDS):
        raise RuntimeError("selected-evidence chunk provenance is incomplete")

    direct_document_chunk = parsed_chunks["15fb5460a23aa10d-paragraph_group-9b55ec13ba82"]
    required_markers = ("필요서류", "서류 구비후", "증빙서류")
    missing_markers = [marker for marker in required_markers if marker not in direct_document_chunk["text"]]
    if missing_markers:
        raise RuntimeError(f"direct original-primary evidence lost document markers: {missing_markers}")

    artifact = {
        "artifact": "P50V3-006 required-fact adjudication",
        "version": 1,
        "hcx_calls": 0,
        "immutable_inputs": {
            "holdout": str(HOLDOUT.relative_to(ROOT)),
            "holdout_sha256": _sha256(HOLDOUT),
            "execution": str(EXECUTION.relative_to(ROOT)),
            "execution_sha256": _sha256(EXECUTION),
            "raw_original_primary_source": str(RAW_SOURCE.relative_to(ROOT)),
            "raw_original_primary_sha256": _sha256(RAW_SOURCE),
            "parsed_original_primary_corpus": str(CHUNKS.relative_to(ROOT)),
        },
        "record_id": RECORD_ID,
        "question": holdout["question"],
        "canonical_requirement": holdout["canonical_requirement"],
        "required_facts": holdout["required_facts"],
        "selected_direct_evidence": [
            {
                "chunk_id": chunk_id,
                "source_path": parsed_chunks[chunk_id]["source_path"],
                "locator": parsed_chunks[chunk_id]["locator"],
                "text": parsed_chunks[chunk_id]["text"],
            }
            for chunk_id in SELECTED_CHUNK_IDS
        ],
        "original_hcx_output": execution["answer"],
        "original_host_completion": execution["host_completion"],
        "document_requirement_markers": list(required_markers),
        "classification": "genuine_required_fact_omission",
        "benchmark_valid": True,
        "reason": (
            "The selected original-primary doc46.pdf evidence explicitly states "
            "'필요서류', '서류 구비후', and '증빙서류'.  The answer's generic "
            "'증빙이 필요' drops the user-actionable document requirement."
        ),
        "allowed_minimal_runtime_change": {
            "layer": "host-owned required-fact completeness",
            "requirement": "DC.early_withdrawal.required_documents",
            "evidence_anchor": "증빙서류",
            "completion_text": "DC 중도인출은 법정사유별로 필요한 증빙서류를 준비해야 합니다.",
            "constraints": [
                "selected evidence must contain the exact evidence anchor",
                "do not add document names",
                "do not add legal-ground lists",
                "do not expand to IRP or adjacent fields",
            ],
        },
        "forbidden_changes": [
            "generator_prompt_final_v2_1",
            "global validator threshold or fuzzy matching",
            "retrieval expansion",
            "holdout manifest or expected required facts",
        ],
        "runtime_patch_applied": False,
    }
    OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "classification": artifact["classification"],
        "benchmark_valid": artifact["benchmark_valid"],
        "hcx_calls": artifact["hcx_calls"],
        "output": str(OUTPUT.relative_to(ROOT)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
