"""Run P44 beside the candidate API path without changing its responses.

This is an integration/containment check, not a live semantic-selector run:
P42's already frozen selector decisions are replayed while the real resolver,
binder, scoped retrieval, direct-field binding, and P27-D candidate API paths
execute.  No HCX request is made.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.api.main import create_app
from src.experiments.direct_requirement_selector import DirectRequirementSelection
from src.experiments.read_only_shadow_integration import ReadOnlyScopedShadowObserver
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.experiments.p27d_structured_output import P27DStructuredOutputAgent
from src.generation.fake import FakeGenerator
from src.orchestration.retrieval_service import build_frozen_retriever


P42 = ROOT / "evaluation/p42_final_frontend_holdout.json"
MANIFEST = ROOT / "question_bank/holdouts/p42_final_frontend_holdout.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
OUTPUT = ROOT / "evaluation/p44_read_only_shadow_integration.json"


class FrozenP42Selector:
    """Replay only frozen selector decisions; resolver/binder still run live."""

    def __init__(self, outputs_by_question: dict[str, dict]):
        self.outputs_by_question = outputs_by_question

    def select(self, question: str, *, allowed_requirements=None, active_subjects=()):
        row = self.outputs_by_question[question]
        selected = tuple(row["selected_requirements"])
        allowed = set(allowed_requirements or row["allowed_requirements"])
        unknown = tuple(item for item in selected if item not in allowed)
        return DirectRequirementSelection(
            selected_requirements=tuple(item for item in selected if item in allowed),
            resolved_product_codes=(),
            unresolved=bool(row["unresolved"]),
            schema_valid=bool(row["schema_valid"]),
            ontology_valid=bool(row["ontology_valid"]) and not unknown,
            unknown_requirements=unknown,
            diagnostic={"source": "P42_frozen_replay", "active_subjects": list(active_subjects)},
        )


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _divergence_class(legacy: dict, shadow) -> tuple[str, str]:
    legacy_ids = {item["chunk_id"] for item in legacy["retrieved_context"]}
    shadow_ids = set(shadow.context_ids)
    if shadow.status == "shadow_exception" or (shadow.status == "prepared" and not shadow_ids):
        return "shadow_worse", "shadow_missing_or_exception"
    if legacy_ids == shadow_ids:
        return "equivalent", "same_context_ids"
    if not legacy["think_trace"].get("evidence_sufficient") and shadow.status == "prepared":
        return "shadow_better", "legacy_insufficient_shadow_prepared"
    return "equivalent", "different_context_requires_source_relevance_not_answer_comparison"


def main() -> None:
    p42 = json.loads(P42.read_text(encoding="utf-8"))
    manifest = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    outputs_by_id = {item["id"]: item for item in p42["outputs"]}
    outputs_by_question = {item["question"]: outputs_by_id[item["id"]] for item in manifest}
    retriever = build_frozen_retriever(CORPUS, INDEX)
    observer = ReadOnlyScopedShadowObserver(
        ResolverFirstScopedSelector(FrozenP42Selector(outputs_by_question)),
        ScopedFrontendPreparationShadow(retriever),
    )
    baseline_client = TestClient(create_app(P27DStructuredOutputAgent(
        build_frozen_retriever(CORPUS, INDEX), FakeGenerator(),
    )))
    observed_client = TestClient(create_app(P27DStructuredOutputAgent(
        build_frozen_retriever(CORPUS, INDEX), FakeGenerator(),
    ), observer))

    rows = []
    for item in manifest:
        request = {"question": item["question"], "top_k": 5}
        before = baseline_client.post("/answer", json=request)
        after = observed_client.post("/answer", json=request)
        if before.status_code != 200 or after.status_code != 200:
            raise RuntimeError(f"candidate API failure for {item['id']}: {before.status_code}/{after.status_code}")
        legacy, observed = before.json(), after.json()
        shadow = observer.records[-1]
        divergence, reason = _divergence_class(legacy, shadow)
        rows.append({
            "id": item["id"],
            "candidate_response_unchanged": legacy == observed,
            "candidate_response_hash": _sha(legacy),
            "shadow": shadow.as_dict(),
            "divergence": divergence,
            "divergence_reason": reason,
            "legacy_context_ids": [value["chunk_id"] for value in legacy["retrieved_context"]],
        })

    latencies = [row["shadow"]["latency_ms"] for row in rows]
    summary = {
        "question_count": len(rows),
        "candidate_response_unchanged": sum(row["candidate_response_unchanged"] for row in rows),
        "shadow_contract_errors": sum(row["shadow"]["status"] == "frontend_contract_error" for row in rows),
        "shadow_exceptions": sum(row["shadow"]["status"] == "shadow_exception" for row in rows),
        "ambiguous_scope_retrieval": sum(
            bool(row["shadow"]["status"] == "unresolved_scope" and row["shadow"]["context_ids"])
            for row in rows
        ),
        "shadow_worse": sum(row["divergence"] == "shadow_worse" for row in rows),
        "shadow_better": sum(row["divergence"] == "shadow_better" for row in rows),
        "equivalent": sum(row["divergence"] == "equivalent" for row in rows),
        "shadow_latency_ms": {
            "min": min(latencies), "median": round(statistics.median(latencies), 3), "max": max(latencies),
        },
        "hcx_answer_calls_added": 0,
        "candidate_decision_changed": False,
        "browser_output_changed": False,
    }
    payload = {
        "experiment": "P44 Read-only Shadow Integration",
        "input": {"p42_frozen_selector_output": str(P42.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT))},
        "boundary": "frozen selector replay + live resolver/binder/retrieval; no HCX, candidate decision, or browser response mutation",
        "summary": summary,
        "rows": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
