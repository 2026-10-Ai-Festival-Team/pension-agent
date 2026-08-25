"""Validate and freeze P45's single-active-subject Closed factual manifest.

P45 deliberately excludes genuine multi-subject comparisons.  That is a
declared frozen capability boundary of ``ResolverFirstScopedSelector``, not a
post-hoc score exclusion: a non-unique active subject must remain unresolved
until the project implements a separate comparison lane.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.direct_requirement_selector import DIRECT_REQUIREMENT_LABELS
from src.orchestration.question_normalizer import normalize_pension_question


HOLDOUT = ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl"
METADATA = ROOT / "question_bank/holdouts/p45_final_single_subject_closed_e2e_metadata.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _questions(path: Path) -> list[str]:
    try:
        if path.suffix == ".jsonl":
            return [row["question"] for row in _rows(path) if isinstance(row.get("question"), str)]
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row["question"] for row in data if isinstance(row, dict) and isinstance(row.get("question"), str)]
        return []
    except (OSError, json.JSONDecodeError):
        return []


def main() -> None:
    rows = _rows(HOLDOUT)
    if len(rows) != 18 or {row["id"] for row in rows} != {f"P45-{index:03d}" for index in range(1, 19)}:
        raise RuntimeError("P45 requires 18 stable manually annotated rows")
    if any(row.get("annotation_source") != "manual" or row.get("auto_converted") for row in rows):
        raise RuntimeError("P45 requires manually annotated, non-auto-converted gold")
    if any(row.get("answerability") != "answerable" for row in rows):
        raise RuntimeError("P45 must be Closed answerable only")
    if any(not isinstance(row.get("expected_active_subject"), str) or not row["expected_active_subject"] for row in rows):
        raise RuntimeError("every P45 row needs exactly one expected active subject")
    if any(row.get("expected_reference_behavior") != "resolved" for row in rows):
        raise RuntimeError("P45 excludes ambiguous and comparison-only scope")
    unknown = sorted({requirement for row in rows for requirement in row["selected_requirements"] if requirement not in DIRECT_REQUIREMENT_LABELS})
    if unknown:
        raise RuntimeError(f"unknown direct requirements: {unknown}")
    if any(set(row["selected_requirements"]) != set(row["gold_evidence"]) for row in rows):
        raise RuntimeError("each selected requirement needs manually fixed gold evidence")
    if any(not all(chunk_ids for chunk_ids in row["gold_evidence"].values()) for row in rows):
        raise RuntimeError("empty gold evidence is not allowed")
    normalized = [normalize_pension_question(row["question"]) for row in rows]
    if len(normalized) != len(set(normalized)):
        raise RuntimeError("P45 contains internal normalized duplicates")
    seen: dict[str, list[str]] = {}
    for pattern in (
        "question_bank/**/*.jsonl", "question_bank/**/*.json", "evaluation/*holdout*.json",
        "evaluation/*holdout*.jsonl", "evaluation/closed_core_benchmark_v1.jsonl",
        "evaluation/question_bank_v1.jsonl",
    ):
        for path in ROOT.glob(pattern):
            if path == HOLDOUT:
                continue
            for question in _questions(path):
                seen.setdefault(normalize_pension_question(question), []).append(str(path.relative_to(ROOT)))
    duplicates = {row["id"]: seen[value] for row, value in zip(rows, normalized) if value in seen}
    if duplicates:
        raise RuntimeError(f"P45 normalized overlap: {duplicates}")
    metadata = {
        "experiment": "P45 Final Fresh Single-Subject Closed E2E",
        "question_count": len(rows),
        "supported_lane": "single-active-subject Closed factual",
        "excluded_capability": "genuine multi-subject comparison; non_unique_active_subject remains unresolved",
        "manifest_sha256": hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "frozen_before_hcx": True,
        "hcx_calls": 0,
    }
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
