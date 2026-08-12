"""Conditional shadow의 generation 전 실행 상태를 결정적으로 구성한다.

P16 Shadow Agent와 offline 진단이 같은 Router, requirement candidate expansion,
gate, context selection 경로를 재사용하도록 한 공용 composition helper다. HCX 호출은
포함하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.requirement_retrieval import expand_requirement_candidates
from src.orchestration.evidence_assessor import EvidenceAssessment


@dataclass(frozen=True)
class ShadowExecutionPlan:
    """HCX 호출 직전까지 확정된 Shadow Agent의 중간 상태."""

    analysis: object
    route: object
    requirement_case: object | None
    base_results: tuple
    candidate_results: tuple
    selection: object | None
    contexts: tuple
    assessment: EvidenceAssessment


def prepare_shadow_execution(
    *,
    question: str,
    top_k: int,
    retriever: object,
    analyzer: object,
    context_builder: object,
    router: object,
    gate: object,
    requirement_retrieval_top_k: int,
) -> ShadowExecutionPlan:
    """P16 Shadow Agent와 동일한 generation 전 composition을 실행한다."""
    analysis = analyzer.analyze(question)
    route = router.classify(analysis)
    base_results = tuple(retriever.search(analysis.question, top_k=top_k).results)
    requirement_case = route.requirement_case
    candidate_results = expand_requirement_candidates(
        requirement_case if route.route == "compound" else None,
        base_results,
        retriever,
        top_k=requirement_retrieval_top_k,
    )
    decision = gate.assess(route.route, analysis, candidate_results, requirement_case)

    selection = None
    if route.route == "compound" and requirement_case is not None:
        selection = gate.selector.select(requirement_case, candidate_results)
        contexts = tuple(selection.contexts)
    else:
        contexts = tuple(context_builder.build(list(base_results), top_k))

    assessment = EvidenceAssessment(
        decision.sufficient,
        decision.reason,
        decision.missing_slots,
        decision.selected_chunk_ids,
    )
    return ShadowExecutionPlan(
        analysis=analysis,
        route=route,
        requirement_case=requirement_case,
        base_results=base_results,
        candidate_results=tuple(candidate_results),
        selection=selection,
        contexts=contexts,
        assessment=assessment,
    )
