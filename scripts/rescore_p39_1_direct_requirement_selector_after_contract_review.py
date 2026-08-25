"""Rescore frozen P39-1 outputs after the pre-holdout gold-contract review.

No HCX call is made.  The raw C selections from the original live run are
reused exactly; only the manually reviewed P38-2-009 required/optional split
changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.direct_requirement_selector_evaluator import (
    frozen_v21_predictions,
    legacy_planner_requirements,
    score_requirement_predictions,
)


GOLD = ROOT / "question_bank/development/p39_1_direct_requirement_selector_gold.jsonl"
ORIGINAL = ROOT / "evaluation/p39_1_direct_requirement_selector_ab.json"
V21_BASELINE = ROOT / "evaluation/p38_7b_v21_ab_p38_2_subset.json"
OUTPUT = ROOT / "evaluation/p39_1_direct_requirement_selector_ab_contract_review.json"


def main() -> None:
    rows = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    c_outputs = original["C_selector_outputs"]
    c_predictions = {item["source_question_id"]: tuple(item["selected_requirements"]) for item in c_outputs}
    a_predictions = {row["source_question_id"]: legacy_planner_requirements(row["question"]) for row in rows}
    b_predictions = frozen_v21_predictions(V21_BASELINE)
    manifest_sha = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    result = {
        "experiment": "P39-1 direct selector rescore after P38-2-009 gold-contract review",
        "live_hcx_calls": 0,
        "frozen_raw_c_output_artifact": str(ORIGINAL.relative_to(ROOT)),
        "input": {"manifest": str(GOLD.relative_to(ROOT)), "manifest_sha256": manifest_sha, "question_count": len(rows)},
        "contract_review": {
            "source_question_id": "P38-2-009",
            "required_requirement_removed": "retirement_pension.in_kind_transfer.definition",
            "reason": "The question requires application routes; transfer definition is optional supporting context.",
        },
        "methods": {
            "A_existing_production_planner": score_requirement_predictions(rows, a_predictions, {"live_hcx_calls": 0, "provider_errors": 0}),
            "B_frozen_p38_v21_atom_parser": score_requirement_predictions(rows, b_predictions, {"live_hcx_calls": 0, "provider_errors": 0}),
            "C_p39_direct_requirement_selector": score_requirement_predictions(rows, c_predictions, original["C_runtime"]),
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {key: value for key, value in metrics.items() if key not in {"details", "runtime"}} for name, metrics in result["methods"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
