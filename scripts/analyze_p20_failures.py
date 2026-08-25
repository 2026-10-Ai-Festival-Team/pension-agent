"""P21: Attribute P20 failures without calling HCX or changing Agent policy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.p20_failure_attribution import summarize


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=ROOT / "data/diagnostics/p20_shadow_hcx.json")
    parser.add_argument("--reviews", type=Path, default=ROOT / "data/diagnostics/p20_shadow_reviewed.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "evaluation/p21_failure_attribution.json")
    args = parser.parse_args()
    payload = json.loads(args.run.read_text(encoding="utf-8"))
    reviews = {item["question_id"]: item for item in _jsonl(args.reviews)}
    result = {
        "run_variant": payload.get("variant"),
        "model": payload.get("model"),
        "preparation_parity": payload.get("p19_preparation_parity"),
        "attribution": summarize(payload["rows"], reviews),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
