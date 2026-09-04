"""Freeze and validate the P39-2 fresh direct-selector holdout (no HCX)."""
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


HOLDOUT = ROOT / "question_bank/holdouts/p39_2_direct_requirement_selector_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p39_2_direct_requirement_selector_holdout_metadata.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _question_texts(path: Path) -> list[str]:
    try:
        if path.suffix == ".jsonl":
            return [row["question"] for row in _rows(path) if isinstance(row.get("question"), str)]
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row["question"] for row in data if isinstance(row, dict) and isinstance(row.get("question"), str)]
    except (json.JSONDecodeError, OSError):
        return []
    return []


def _existing_question_index() -> dict[str, list[str]]:
    patterns = (
        "question_bank/**/*.jsonl", "question_bank/**/*.json",
        "evaluation/*holdout*.json", "evaluation/*holdout*.jsonl",
        "evaluation/closed_core_benchmark_v1.jsonl",
        "evaluation/question_bank_v1.jsonl",
    )
    index: dict[str, list[str]] = {}
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if path == HOLDOUT:
                continue
            for question in _question_texts(path):
                index.setdefault(normalize_pension_question(question), []).append(str(path.relative_to(ROOT)))
    return index


def main() -> None:
    rows = _rows(HOLDOUT)
    required_categories = {"institution", "tax", "procedure", "compound_closed", "product_factual", "product_comparison"}
    if len(rows) != 18:
        raise RuntimeError(f"P39-2 requires 18 rows, found {len(rows)}")
    if {row["category"] for row in rows} != required_categories:
        raise RuntimeError("P39-2 must have all six balanced Closed factual categories")
    if any(sum(row["category"] == category for row in rows) != 3 for category in required_categories):
        raise RuntimeError("P39-2 must have exactly three rows per category")
    if any(row.get("annotation_source") != "manual" or row.get("auto_converted") for row in rows):
        raise RuntimeError("P39-2 gold must be manually confirmed and non-auto-converted")
    unknown = sorted({value for row in rows for value in row["selected_requirements"] if value not in DIRECT_REQUIREMENT_LABELS})
    if unknown:
        raise RuntimeError(f"P39-2 has unknown direct requirements: {unknown}")
    normalized = [normalize_pension_question(row["question"]) for row in rows]
    if len(set(normalized)) != len(normalized):
        raise RuntimeError("P39-2 contains normalized duplicates internally")
    existing = _existing_question_index()
    duplicates = {row["id"]: existing[normal] for row, normal in zip(rows, normalized) if normal in existing}
    if duplicates:
        raise RuntimeError(f"P39-2 overlaps existing normalized questions: {duplicates}")
    manifest_sha = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    metadata = {
        "experiment": "P39-2 Fresh Direct-Selector Holdout",
        "question_count": len(rows),
        "category_counts": {category: 3 for category in sorted(required_categories)},
        "manifest_sha256": manifest_sha,
        "duplicate_check": "normalize_pension_question exact normalized overlap against question_bank and holdout/Closed-Core evaluation assets",
        "unknown_enum_values": unknown,
        "frozen_before_hcx": True,
        "hcx_calls": 0,
    }
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
