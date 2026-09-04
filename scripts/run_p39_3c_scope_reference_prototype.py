"""Run P39-3C without HCX against frozen P39-3 selector outputs."""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver


INPUT = ROOT / "evaluation/p39_3_fresh_direct_requirement_selector_holdout.json"
OUTPUT = ROOT / "evaluation/p39_3c_scope_reference_prototype.json"


def main() -> None:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    questions = {(item["id"] if "id" in item else item["source_question_id"]): item["question"] for item in source["metrics"]["details"]}
    resolver, binder = ScopeReferenceResolver(), DeterministicBinder()
    rows = []
    for item in source["selector_outputs"]:
        resolution = resolver.resolve(questions[item["id"]])
        binding = binder.bind(questions[item["id"]], resolution, tuple(item["selected_requirements"]))
        rows.append({"id": item["id"], "question": questions[item["id"]], "frozen_output_hash": item["output_hash"], "resolution": resolution.as_dict(), "binding": binding.as_dict()})
    lookup = {row["id"]: row for row in rows}
    acceptance = {
        "p39_3_001_active_dc": lookup["P39-3-001"]["resolution"]["active_subjects"] == ["DC"],
        "p39_3_001_conflict_detected": bool(lookup["P39-3-001"]["binding"]["scope_conflicts"]),
        "p39_3_003_incomplete_detected": "selector_multi_requirement_incomplete:operation_party" in lookup["P39-3-003"]["binding"]["incomplete_reasons"],
        "p39_3_018_second_product_only": lookup["P39-3-018"]["resolution"]["active_subjects"] == ["product:KR5114450222"],
        "hcx_calls": 0,
        "candidate_agent_changed": False,
    }
    result = {"experiment": "P39-3C Scope/Reference Resolver + Binder Prototype", "input": str(INPUT.relative_to(ROOT)), "selector_enum_prompt_changed": False, "rows": rows, "acceptance": acceptance}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(acceptance, ensure_ascii=False))


if __name__ == "__main__":
    main()
