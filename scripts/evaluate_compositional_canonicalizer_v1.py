"""Run the isolated P38-1 compositional-parser baseline (no HCX/API calls)."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.compositional_evaluator import evaluate


OUTPUT = ROOT / "evaluation/regressions/p38_1_compositional_parser_baseline.json"


def main() -> None:
    result = evaluate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "subjects_f1": result["component_metrics"]["subjects"]["f1"],
        "actions_f1": result["component_metrics"]["actions"]["f1"],
        "fields_f1": result["component_metrics"]["fields"]["f1"],
        "modifiers_f1": result["component_metrics"]["modifiers"]["f1"],
        "requirement_exact": result["requirement_composition"],
        "output": str(OUTPUT.relative_to(ROOT)),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
