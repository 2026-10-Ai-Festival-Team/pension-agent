"""Build a non-frozen P49 human-review candidate from team and v5 drafts.

The team file is compared against the P49-2G6 evidence-first remediated v5
draft.  v5 stays authoritative for evidence text and completed P49-2G6 fixes.
The one adopted team change removes an ungrounded ordinal statement from
P45-013.  Corpus metadata is attached to every cited evidence item so product
provenance is visible in the review record itself.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "evaluation/fine_tuning"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
TEAM_GOLD = BASE / "refine_p49_draft_gold_training_records_v2.jsonl"
V5_GOLD = BASE / "p49_draft_gold_training_records_v5.jsonl"
V5_CONTRASTIVE = BASE / "p49_draft_contrastive_records_v5.jsonl"
OUT_GOLD = BASE / "p49_human_review_candidate_gold_v6.jsonl"
OUT_CONTRASTIVE = BASE / "p49_human_review_candidate_contrastive_v6.jsonl"
OUT_LEDGER = BASE / "p49_human_review_ledger_v6.jsonl"
OUT_MANIFEST = BASE / "p49_team_merge_review_candidate_v6_manifest.json"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")


def enrich_evidence(record: dict, corpus: dict[str, dict]) -> dict:
    enriched = []
    for evidence in record["direct_evidence"]:
        source = corpus[evidence["chunk_id"]]
        if evidence["text"] != source["text"]:
            raise RuntimeError(f"v5 evidence text diverges from corpus: {record['record_id']} / {evidence['chunk_id']}")
        enriched.append({
            **evidence,
            "source_path": source.get("source_path"),
            "product_codes": source.get("product_codes", []),
        })
    return {**record, "direct_evidence": enriched}


def set_pending_human_review(record: dict) -> dict:
    quality = {
        **record["quality"],
        "manual_review": "pending_p49_team_merge_human_approval",
    }
    return {**record, "quality": quality}


def adopt_p45_013_ordinal_fix(record: dict, team: dict) -> dict:
    """Remove an ordinal assertion that is not needed for the generator task."""
    assert record["record_id"] == "positive_draft-p45-013"
    assert record["question"] == team["question"]
    completion = team["completion"].replace(
        "[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.",
        "[유의사항] 없음",
    )
    quality = {
        **record["quality"],
        "required_facts": team["quality"]["required_facts"],
        "manual_review": "pending_p49_team_merge_human_approval",
    }
    return {
        **record,
        "completion": completion,
        "factual_claims": team["factual_claims"],
        "evidence_anchors": team["evidence_anchors"],
        "quality": quality,
    }


def main() -> None:
    corpus = {record["chunk_id"]: record for record in load(CORPUS)}
    team = {record["record_id"]: record for record in load(TEAM_GOLD)}
    gold = load(V5_GOLD)
    contrastive = load(V5_CONTRASTIVE)
    if len(gold) != 19 or len(contrastive) != 19 or len(team) != 19:
        raise RuntimeError("expected 19 team gold, 19 v5 gold, and 19 v5 contrastive records")
    if set(team) != {record["record_id"] for record in gold}:
        raise RuntimeError("team and v5 positive record IDs differ")

    final_gold = []
    for record in gold:
        merged = set_pending_human_review(enrich_evidence(record, corpus))
        if merged["record_id"] == "positive_draft-p45-013":
            merged = adopt_p45_013_ordinal_fix(merged, team[merged["record_id"]])
        final_gold.append(merged)
    final_contrastive = [set_pending_human_review(enrich_evidence(record, corpus)) for record in contrastive]
    write(OUT_GOLD, final_gold)
    write(OUT_CONTRASTIVE, final_contrastive)
    write(OUT_LEDGER, [
        {
            "record_id": record["record_id"],
            "review_status": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "reviewer_note": None,
            "review_criteria": [
                "question_requirement_alignment",
                "required_fact_completeness",
                "direct_evidence_grounding",
                "adjacent_field_precision",
                "answer_format_quality",
            ],
        }
        for record in (*final_gold, *final_contrastive)
    ])

    manifest = {
        "stage": "P49 Team Gold Comparison → Human Review Candidate v6",
        "status": "not_frozen_human_approval_pending",
        "record_counts": {"gold": len(final_gold), "contrastive": len(final_contrastive), "total": len(final_gold) + len(final_contrastive)},
        "base": V5_GOLD.name,
        "team_reference": TEAM_GOLD.name,
        "adopted_team_changes": {
            "positive_draft-p45-013": "removed the unnecessary ordinal assertion; direct product code remains the grounded answer target"
        },
        "retained_v5_remediations": [
            "header-preserving evidence for P45/P48-011",
            "판매회사 보수 rather than unsupported 판매수수료 field",
            "annual total-fee wording rather than one-year cost wording",
            "minimum-threshold wording for P48-002",
            "IRP tax-timing completion with both operating and payout timing",
            "complete historical risk-grade table coverage for P48-009",
            "supported_answer/full outcome contract and non-meta notice style",
        ],
        "corpus_provenance_enriched": True,
        "sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (TEAM_GOLD, V5_GOLD, V5_CONTRASTIVE, OUT_GOLD, OUT_CONTRASTIVE, OUT_LEDGER)
        },
        "next_allowed_stage": "P49-2G human approval of all 38 v6 candidate records",
        "training_export_allowed": False,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gold": len(final_gold), "contrastive": len(final_contrastive), "adopted_team_changes": 1}, ensure_ascii=False))


if __name__ == "__main__":
    main()
