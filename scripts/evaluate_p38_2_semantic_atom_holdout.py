"""Evaluate frozen P38-2 with the isolated parser only; never call HCX."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.compositional_evaluator import evaluate


GOLD = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout.jsonl"
METADATA = ROOT / "question_bank/holdouts/p38_2_semantic_atom_holdout_metadata.json"
OUTPUT = ROOT / "evaluation/p38_2_semantic_atom_holdout_results.json"


def main() -> None:
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    result = evaluate(gold_path=GOLD)
    result["holdout"] = {
        "manifest_sha256": metadata["manifest_sha256"],
        "status": metadata["status"],
        "go_criteria": metadata["go_criteria"],
    }
    result["hcx_calls"] = 0
    result["candidate_agent_changed"] = False
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "component_f1": {name: value["f1"] for name, value in result["component_metrics"].items()},
        "requirement_exact": result["requirement_composition"],
        "hcx_calls": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
