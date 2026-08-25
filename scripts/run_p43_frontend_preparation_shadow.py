"""Compare frozen P42 front-end preparation with the existing candidate path.

No HCX call, answer generation, browser behavior, or candidate mutation occurs.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


P42 = ROOT / "evaluation/p42_final_frontend_holdout.json"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
OUTPUT = ROOT / "evaluation/p43_frontend_preparation_shadow.json"


def main() -> None:
    p42 = json.loads(P42.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (ROOT / "question_bank/holdouts/p42_final_frontend_holdout.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    frontend = {item["id"]: item for item in p42["outputs"]}
    retriever = build_frozen_retriever(CORPUS, INDEX)
    legacy = P27DStructuredOutputAgent(retriever=retriever, generator=FakeGenerator())
    shadow = ScopedFrontendPreparationShadow(retriever)
    output_rows = []
    for row in rows:
        legacy_plan = legacy.prepare(row["question"], top_k=5)
        new_plan = shadow.prepare(row["question"], frontend[row["id"]])
        legacy_context_ids = [item.chunk_id for item in legacy_plan.contexts]
        new_context_ids = [item.chunk_id for item in new_plan.contexts]
        output_rows.append({
            "id": row["id"],
            "question": row["question"],
            "frontend_status": new_plan.status,
            "frontend_active_subject": new_plan.active_subject,
            "frontend_requirements": list(new_plan.selected_requirements),
            "frontend_requirement_candidates": {key: list(value) for key, value in new_plan.requirement_candidates.items()},
            "frontend_context_ids": new_context_ids,
            "legacy_route": legacy_plan.route.route,
            "legacy_requirement_slots": [slot.key for slot in legacy_plan.requirement_case.slots] if legacy_plan.requirement_case else [],
            "legacy_context_ids": legacy_context_ids,
            "legacy_evidence_sufficient": legacy_plan.assessment.sufficient,
            "context_overlap_ids": sorted(set(legacy_context_ids) & set(new_context_ids)),
            "legacy_only_context_ids": sorted(set(legacy_context_ids) - set(new_context_ids)),
            "frontend_only_context_ids": sorted(set(new_context_ids) - set(legacy_context_ids)),
            "diverged": legacy_context_ids != new_context_ids,
        })
    summary = {
        "question_count": len(output_rows),
        "frontend_prepared": sum(item["frontend_status"] == "prepared" for item in output_rows),
        "frontend_unresolved_scope": sum(item["frontend_status"] == "unresolved_scope" for item in output_rows),
        "frontend_contract_errors": sum(item["frontend_status"] == "frontend_contract_error" for item in output_rows),
        "context_divergences": sum(item["diverged"] for item in output_rows),
        "legacy_evidence_sufficient": sum(item["legacy_evidence_sufficient"] for item in output_rows),
        "hcx_calls": 0,
        "candidate_agent_changed": False,
        "browser_changed": False,
    }
    payload = {
        "experiment": "P43 Front-End Preparation Shadow",
        "inputs": {
            "p42_frozen_output": str(P42.relative_to(ROOT)),
            "corpus": str(CORPUS.relative_to(ROOT)),
            "index": str(INDEX.relative_to(ROOT)),
        },
        "boundary": "preparation-only; no new frontend output reaches answer generation",
        "summary": summary,
        "rows": output_rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
