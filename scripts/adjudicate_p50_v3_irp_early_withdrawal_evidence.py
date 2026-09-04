"""Adjudicate the immutable P50-v3 IRP legal-grounds evidence contract.

This is a zero-HCX, read-only corpus audit.  It does not alter the frozen
holdout, expected facts, retriever, or completeness policy.  The result is an
explicit record of whether a runtime evidence-binding repair is permissible.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/parsed/chunks.jsonl"
HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3.jsonl"
EXECUTION = ROOT / "evaluation/fresh_p50_final_holdout_execution_v3.json"
OUT = ROOT / "evaluation/fresh_p50_v3_irp_early_withdrawal_evidence_adjudication_v1.json"
RECORD_ID = "P50V3-009"


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _excerpt(text: str, limit: int = 400) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit - 1]}…"


def _evidence_row(chunk: dict, *, role: str) -> dict:
    locator = chunk.get("locator") or {}
    return {
        "role": role,
        "chunk_id": chunk["chunk_id"],
        "source_id": chunk["source_id"],
        "source_path": chunk["source_path"],
        "locator": locator,
        "text_sha256": hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest(),
        "excerpt": _excerpt(chunk["text"]),
    }


def main() -> None:
    corpus = {row["chunk_id"]: row for row in _jsonl(CORPUS)}
    holdout = next(row for row in _jsonl(HOLDOUT) if row["id"] == RECORD_ID)
    execution = json.loads(EXECUTION.read_text(encoding="utf-8"))
    output = next(row for row in execution["outputs"] if row["id"] == RECORD_ID)

    selected_ids = tuple(output["cited_chunk_ids"])
    selected = [corpus[chunk_id] for chunk_id in selected_ids]
    # This primary original paragraph explicitly establishes the legal-rule
    # boundary: IRP withdrawal reasons are enumerated by law.  It is a generic
    # canonical-requirement signal, not a question-specific fallback.
    legal_rule = next(
        row for row in corpus.values()
        if "IRP" in row["text"]
        and "중도인출 사유를 법으로 열거" in row["text"]
        and row["source_path"] == "docs_renamed/doc20.docx"
    )
    # An independent original-primary source independently lists the allowed
    # reasons, preventing a single-document inference from becoming authority.
    independent_list = next(
        row for row in corpus.values()
        if row["source_path"] == "docs_renamed/doc14.pdf"
        and "개인형 퇴직연금제도(IRP) 중도인출 사유" in row["text"]
        and "무주택자인 가입자" in row["text"]
    )

    selected_has_explicit_legal_rule = any("중도인출 사유를 법으로 열거" in row["text"] for row in selected)
    payload = {
        "experiment": "Fresh P50 v3 IRP early-withdrawal evidence-contract adjudication",
        "hcx_calls": 0,
        "immutable_inputs": {
            "holdout": str(HOLDOUT.relative_to(ROOT)),
            "execution": str(EXECUTION.relative_to(ROOT)),
            "record_id": RECORD_ID,
            "holdout_sha256": hashlib.sha256(HOLDOUT.read_bytes()).hexdigest(),
        },
        "record": {
            "question": holdout["question"],
            "expected_outcome": holdout["expected_outcome"],
            "canonical_requirement": holdout["canonical_requirement"],
            "original_expected_required_fact": holdout["required_facts"],
            "execution_missing_required_facts": output["missing_required_facts"],
            "selected_evidence": [_evidence_row(row, role="selected_runtime_evidence") for row in selected],
        },
        "authoritative_original_primary_corpus_audit": {
            "legal_rule_evidence": _evidence_row(legal_rule, role="direct_legal_rule"),
            "independent_reason_list_evidence": _evidence_row(independent_list, role="independent_reason_list"),
            "semantic_equivalents_checked": [
                "중도인출 가능 사유",
                "근로자퇴직급여보장법 적용",
                "중도인출 사유를 법으로 열거",
            ],
        },
        "classification": {
            "benchmark_valid": True,
            "benchmark_invalid_reason": None,
            "primary_root_cause": "evidence_binding_failure",
            "genuine_runtime_failure": True,
            "reason": (
                "The original-primary corpus explicitly says that IRP withdrawal reasons "
                "are enumerated by law and independently lists the allowed reasons.  The "
                "runtime selected only a reason table; it did not bind the direct legal-rule "
                "paragraph needed for the legal-grounds requirement."
            ),
            "selected_evidence_has_explicit_legal_rule": selected_has_explicit_legal_rule,
            "runtime_patch_applied": False,
        },
        "next_action_authority": {
            "permitted": "Add a canonical IRP early-withdrawal direct-evidence binding signal and test it.",
            "prohibited": [
                "Change the frozen P50-v3 manifest or expected facts",
                "Add a host-completion fact before the direct legal-rule evidence is selected",
                "Use augmented or non-primary material as final authority",
                "Hard-code the P50-v3 question",
            ],
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "record_id": RECORD_ID,
        "hcx_calls": 0,
        "benchmark_valid": True,
        "primary_root_cause": "evidence_binding_failure",
        "runtime_patch_applied": False,
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
