"""Extract only evidence-verified generation failures into P49 seed records.

Seeds are not training examples: they deliberately have no completion. A seed
must be manually expanded into a canonical P49 training record after positive
and contrastive examples are authored and Dataset QA passes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OUTPUT = ROOT / "evaluation/fine_tuning/p49_generation_failure_seeds.jsonl"
SUMMARY = ROOT / "evaluation/fine_tuning/p49_generation_failure_seed_summary.json"
SOURCES = {
    "P45": {
        "result": ROOT / "evaluation/p45_final_single_subject_closed_e2e.json",
        "labels": ROOT / "evaluation/p45_final_single_subject_closed_e2e_semantic_labels.json",
        "manifest": ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl",
    },
    "P46": {
        "result": ROOT / "evaluation/p46_final_single_subject_closed_e2e.json",
        "labels": ROOT / "evaluation/p46_final_single_subject_closed_e2e_semantic_labels.json",
        "manifest": ROOT / "question_bank/holdouts/p46_final_single_subject_closed_e2e.jsonl",
    },
    "P47": {
        "result": ROOT / "evaluation/p47_final_single_subject_closed_e2e.json",
        "labels": ROOT / "evaluation/p47_final_single_subject_closed_e2e_semantic_labels.json",
        "manifest": ROOT / "question_bank/holdouts/p47_final_single_subject_closed_e2e.jsonl",
    },
    "P48": {
        "result": ROOT / "evaluation/p48_final_single_subject_closed_e2e.json",
        "labels": ROOT / "evaluation/p48_final_single_subject_closed_e2e_semantic_labels.json",
        "manifest": ROOT / "question_bank/holdouts/p48_final_single_subject_closed_e2e.jsonl",
    },
}
# `field_confusion` is the legacy owner spelling used in P45.  P48 introduced
# the more explicit `generation_field_confusion`; both denote an answer-stage
# failure only after the frozen context was manually verified.
GENERATION_OWNERS = {
    "generation_omission",
    "generation_misread",
    "generation_field_confusion",
    "field_confusion",
}

# This is an evaluation-data taxonomy, never an Agent runtime rule.  Each
# seed was manually attributed after its frozen E2E run.
FAMILY_BY_CASE = {
    "P45-010": "field_distinction", "P45-011": "table_enumeration_completeness",
    "P45-013": "field_distinction", "P45-015": "table_enumeration_completeness",
    "P45-016": "field_distinction", "P45-018": "required_field_completeness",
    "P46-009": "table_enumeration_completeness", "P46-013": "table_enumeration_completeness",
    "P46-016": "required_field_completeness",
    "P47-008": "required_field_completeness", "P47-010": "field_distinction",
    "P47-014": "table_enumeration_completeness",
    "P48-002": "evidence_fidelity", "P48-005": "evidence_fidelity",
    "P48-008": "required_field_completeness", "P48-009": "table_enumeration_completeness",
    "P48-010": "field_distinction", "P48-011": "table_enumeration_completeness",
    "P48-014": "field_distinction",
}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _canonical_manifest_sha256(rows: list[dict]) -> str:
    """Match the canonical manifest hash recorded by the frozen E2E harness."""
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    corpus = {row["chunk_id"]: row for row in _jsonl(ROOT / "data/parsed/chunks.jsonl")}
    seeds = []
    source_hashes = {}
    label_hashes = {}
    manifest_hashes = {}
    for experiment, paths in SOURCES.items():
        raw_bytes = paths["result"].read_bytes()
        source_hashes[experiment] = hashlib.sha256(raw_bytes).hexdigest()
        result = json.loads(raw_bytes)
        label_bytes = paths["labels"].read_bytes()
        label_hashes[experiment] = hashlib.sha256(label_bytes).hexdigest()
        labels = json.loads(label_bytes)
        if labels.get("source_result") != str(paths["result"].relative_to(ROOT)):
            raise RuntimeError(f"{experiment} labels do not identify the frozen raw result")
        manifest_rows = _jsonl(paths["manifest"])
        manifest_hashes[experiment] = _canonical_manifest_sha256(manifest_rows)
        if result.get("manifest_sha256") != manifest_hashes[experiment]:
            raise RuntimeError(f"{experiment} raw result does not match frozen manifest")
        manifest = {row["id"]: row for row in manifest_rows}
        outputs = {row["id"]: row for row in result["outputs"]}
        for label in labels["labels"]:
            if label.get("primary_owner") not in GENERATION_OWNERS:
                continue
            case_id = label["id"]
            if case_id not in FAMILY_BY_CASE:
                raise RuntimeError(f"missing family classification: {case_id}")
            row, output = manifest[case_id], outputs[case_id]
            if output["answer_hash"] != label["answer_hash"]:
                raise RuntimeError(f"answer hash mismatch: {case_id}")
            gold_ids = tuple(dict.fromkeys(chunk_id for ids in row["gold_evidence"].values() for chunk_id in ids))
            retrieved = set(output.get("retrieved_chunk_ids", ()))
            if not set(gold_ids) <= retrieved:
                raise RuntimeError(f"gold direct evidence not in frozen context: {case_id}")
            direct_evidence = []
            for chunk_id in gold_ids:
                chunk = corpus.get(chunk_id)
                if not chunk:
                    raise RuntimeError(f"missing corpus chunk: {chunk_id}")
                direct_evidence.append({"chunk_id": chunk_id, "text": chunk["text"], "provenance": "original_primary"})
            seeds.append({
                "schema_version": "p49.generation_failure_seed.v1",
                "record_type": "seed_failure",
                "seed_id": f"seed-{case_id.lower()}",
                "source": {"experiment": experiment, "question_id": case_id, "raw_result_sha256": source_hashes[experiment], "answer_hash": label["answer_hash"]},
                "question": row["question"],
                "selected_requirements": row["selected_requirements"],
                "direct_evidence": direct_evidence,
                "required_facts": row["critical_facts"],
                "forbidden_claims": row["forbidden_claims"],
                "failure_owner": label["primary_owner"],
                "failure_family": FAMILY_BY_CASE[case_id],
                "promotion_status": "seed_only_manual_completion_required"
            })
    if len(seeds) != len(FAMILY_BY_CASE) or {seed["source"]["question_id"] for seed in seeds} != set(FAMILY_BY_CASE):
        raise RuntimeError("P49 seed extraction is incomplete")
    OUTPUT.write_text("".join(json.dumps(seed, ensure_ascii=False) + "\n" for seed in seeds), encoding="utf-8")
    family_counts = {}
    for seed in seeds:
        family_counts[seed["failure_family"]] = family_counts.get(seed["failure_family"], 0) + 1
    summary = {
        "seed_count": len(seeds),
        "family_counts": family_counts,
        "source_result_hashes": source_hashes,
        "semantic_label_hashes": label_hashes,
        "manifest_hashes": manifest_hashes,
        "tuning_api_calls": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
