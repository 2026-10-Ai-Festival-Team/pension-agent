"""Run the bounded HCX smoke for repaired P50-v3 runtime failure classes.

The P50-v3 manifest remains immutable.  The exposed failure rows are used only
as regression cases, with four neighbor/negative controls that exercise the
same generalized policies.  A failed smoke never triggers a full P50 run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_fresh_p50_v2_final_holdout import _evaluate
from scripts.run_p45_final_single_subject_closed_e2e import PACING_SECONDS, _settings
from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import HCXDirectRequirementSelector
from src.experiments.scoped_direct_requirement_selector import ResolverFirstScopedSelector
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.hcx import HyperClovaXGenerator
from src.generation.rate_limit import GlobalMinIntervalLimiter
from src.orchestration.retrieval_service import build_frozen_retriever


HOLDOUT = ROOT / "question_bank/holdouts/fresh_p50_final_holdout_v3.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
INDEX = ROOT / "data/indexes/bm25/simple"
EXPOSED_IDS = (
    "P50V3-002", "P50V3-009", "P50V3-023", "P50V3-026", "P50V3-028",
    "P50V3-034", "P50V3-036", "P50V3-039", "P50V3-040", "P50V3-045", "P50V3-049",
)
CONTROLS = (
    {
        "id": "P50V3R-012", "type": "selector_neighbor",
        "question": "DB형 퇴직급여는 퇴직 전 평균임금과 계속근로기간을 기준으로 계산하나요?",
        "expected_outcome": "supported_answer", "expected_active_subject": "DB",
        "selected_requirements": ["DB.benefit_determination"],
        "required_facts": ["평균임금", "계속근로기간"],
        "criteria": {"citation_required": True},
    },
    {
        "id": "P50V3R-013", "type": "clarification_neighbor",
        "question": "연금저축과 IRP 중 내게 더 나은 상품을 추천해줘.",
        "expected_outcome": "clarification_required", "expected_active_subject": None,
        "selected_requirements": [], "required_facts": ["투자 기간"],
        "criteria": {"minimum_clarification": True},
    },
    {
        "id": "P50V3R-014", "type": "personal_recommendation_negative_control",
        "question": "내 개인 IRP에서 ETF 비중을 정해줘.",
        "expected_outcome": "clarification_required", "expected_active_subject": None,
        "selected_requirements": [], "required_facts": ["투자 기간"],
        "criteria": {"minimum_clarification": True},
    },
    {
        "id": "P50V3R-015", "type": "required_fact_neighbor",
        "question": "IRP는 아무 이유 없이 중도인출할 수 있나요, 아니면 법정사유가 필요한가요?",
        "expected_outcome": "supported_answer", "expected_active_subject": "IRP",
        "selected_requirements": ["IRP.early_withdrawal.allowed_reasons"],
        "required_facts": ["법정사유"],
        "criteria": {"citation_required": True},
    },
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--revision", type=int, default=1)
    args = parser.parse_args()
    if not args.execute:
        parser.error("pass --execute to perform the one bounded smoke")
    if args.revision < 1:
        parser.error("revision must be positive")
    output_path = ROOT / f"evaluation/fresh_p50_v3_runtime_repair_smoke_v{args.revision}.json"
    if output_path.exists():
        raise RuntimeError("smoke artifact already exists; duplicate HCX calls are prohibited")

    immutable_rows = {row["id"]: row for row in (
        json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()
    )}
    if set(EXPOSED_IDS) - set(immutable_rows):
        raise RuntimeError("P50-v3 source rows are missing")
    rows = [immutable_rows[record_id] for record_id in EXPOSED_IDS] + list(CONTROLS)

    settings = _settings()
    limiter = GlobalMinIntervalLimiter(PACING_SECONDS, guard_seconds=settings.hcx_pacing_guard_seconds)
    agent = DirectRequirementE2EAgent(
        scoped_selector=ResolverFirstScopedSelector(HCXDirectRequirementSelector(config=settings, rate_limiter=limiter)),
        preparation=ScopedFrontendPreparationShadow(build_frozen_retriever(CORPUS, INDEX)),
        generator=HyperClovaXGenerator(config=settings, rate_limiter=limiter),
    )
    outputs = []
    for row in rows:
        started = time.perf_counter()
        outputs.append(_evaluate(row, agent.answer(row["question"]), (time.perf_counter() - started) * 1000))

    failures = {item["id"]: item["failure_classes"] for item in outputs if item["failure_classes"]}
    failure_classes = sorted({failure for values in failures.values() for failure in values})
    payload = {
        "experiment": "P50 v3 minimal-runtime-repair failure-class smoke",
        "source_holdout": str(HOLDOUT.relative_to(ROOT)),
        "source_manifest_modified": False,
        "record_count": len(rows),
        "exposed_regression_record_ids": list(EXPOSED_IDS),
        "control_record_ids": [row["id"] for row in CONTROLS],
        "generator_model": settings.hcx_model,
        "outputs": outputs,
        "decision": "PASS" if not failures else "FAIL",
        "failure_classes": failure_classes,
        "failures": failures,
        "next_action": "v3_regression_allowed" if not failures else "stop_before_v3_regression",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": payload["decision"], "record_count": len(rows),
        "failure_classes": failure_classes, "next_action": payload["next_action"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
