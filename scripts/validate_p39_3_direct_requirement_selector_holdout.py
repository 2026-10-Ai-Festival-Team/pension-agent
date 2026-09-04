"""Freeze and validate P39-3 after the invalid P39-2 run (no HCX)."""
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


HOLDOUT = ROOT / "question_bank/holdouts/p39_3_direct_requirement_selector_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p39_3_direct_requirement_selector_holdout_metadata.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _texts(path: Path) -> list[str]:
    try:
        if path.suffix == ".jsonl":
            return [row["question"] for row in _rows(path) if isinstance(row.get("question"), str)]
        data = json.loads(path.read_text(encoding="utf-8"))
        return [row["question"] for row in data if isinstance(row, dict) and isinstance(row.get("question"), str)] if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def main() -> None:
    rows = _rows(HOLDOUT)
    categories = {"institution", "tax", "procedure", "compound_closed", "product_factual", "product_comparison"}
    if len(rows) != 18 or {row["category"] for row in rows} != categories or any(sum(row["category"] == category for row in rows) != 3 for category in categories):
        raise RuntimeError("P39-3 requires 18 rows balanced across six Closed factual categories")
    if any(row.get("annotation_source") != "manual" or row.get("auto_converted") for row in rows):
        raise RuntimeError("P39-3 needs manual non-auto-converted gold")
    unknown = sorted({value for row in rows for value in row["selected_requirements"] if value not in DIRECT_REQUIREMENT_LABELS})
    if unknown:
        raise RuntimeError(f"unknown direct requirements: {unknown}")
    normalized = [normalize_pension_question(row["question"]) for row in rows]
    if len(normalized) != len(set(normalized)):
        raise RuntimeError("normalized internal duplicate")
    existing: dict[str, list[str]] = {}
    for pattern in ("question_bank/**/*.jsonl", "question_bank/**/*.json", "evaluation/*holdout*.json", "evaluation/*holdout*.jsonl", "evaluation/closed_core_benchmark_v1.jsonl", "evaluation/question_bank_v1.jsonl"):
        for path in ROOT.glob(pattern):
            if path == HOLDOUT:
                continue
            for question in _texts(path):
                existing.setdefault(normalize_pension_question(question), []).append(str(path.relative_to(ROOT)))
    duplicates = {row["id"]: existing[normal] for row, normal in zip(rows, normalized) if normal in existing}
    if duplicates:
        raise RuntimeError(f"normalized duplicate with existing asset: {duplicates}")
    metadata = {
        "experiment": "P39-3 Fresh Direct-Selector Holdout",
        "supersedes": "P39-2 invalid execution incident; no P39-2 result was retained",
        "question_count": 18,
        "category_counts": {category: 3 for category in sorted(categories)},
        "manifest_sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        "unknown_enum_values": [], "frozen_before_hcx": True, "hcx_calls": 0,
    }
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
