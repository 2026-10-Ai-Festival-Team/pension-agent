"""Validate and freeze P40 scope/reference holdout before any HCX call."""
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

HOLDOUT = ROOT / "question_bank/holdouts/p40_scope_reference_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p40_scope_reference_holdout_metadata.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _questions(path: Path) -> list[str]:
    try:
        if path.suffix == ".jsonl":
            return [row["question"] for row in _rows(path) if isinstance(row.get("question"), str)]
        data = json.loads(path.read_text(encoding="utf-8"))
        return [row["question"] for row in data if isinstance(row, dict) and isinstance(row.get("question"), str)] if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def main() -> None:
    rows = _rows(HOLDOUT)
    if len(rows) != 18 or len({row["id"] for row in rows}) != 18:
        raise RuntimeError("P40 requires 18 uniquely identified rows")
    if any(row.get("annotation_source") != "manual" or row.get("auto_converted") for row in rows):
        raise RuntimeError("P40 must use manual non-auto-converted gold")
    unknown = sorted({item for row in rows for item in row["selected_requirements"] if item not in DIRECT_REQUIREMENT_LABELS})
    if unknown:
        raise RuntimeError(f"unknown direct requirements: {unknown}")
    normalized = [normalize_pension_question(row["question"]) for row in rows]
    if len(normalized) != len(set(normalized)):
        raise RuntimeError("P40 has an internal normalized duplicate")
    seen: dict[str, list[str]] = {}
    for pattern in ("question_bank/**/*.jsonl", "question_bank/**/*.json", "evaluation/*holdout*.json", "evaluation/*holdout*.jsonl", "evaluation/closed_core_benchmark_v1.jsonl", "evaluation/question_bank_v1.jsonl"):
        for path in ROOT.glob(pattern):
            if path == HOLDOUT:
                continue
            for question in _questions(path):
                seen.setdefault(normalize_pension_question(question), []).append(str(path.relative_to(ROOT)))
    duplicates = {row["id"]: seen[value] for row, value in zip(rows, normalized) if value in seen}
    if duplicates:
        raise RuntimeError(f"P40 normalized overlap: {duplicates}")
    metadata = {"experiment": "P40 Fresh Scope/Reference Holdout", "question_count": len(rows), "manifest_sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(), "unknown_enum_values": [], "frozen_before_hcx": True, "hcx_calls": 0}
    METADATA.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
