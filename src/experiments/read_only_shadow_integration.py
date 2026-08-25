"""P44 read-only observer for the scoped direct-selector experiment.

It deliberately has no dependency on candidate answer generation, citation,
policy, or API response schemas.  Every failure is captured as an observation
instead of being propagated to the user request.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import time


@dataclass(frozen=True)
class ShadowObservation:
    question_sha256: str
    status: str
    active_subject: str | None
    selected_requirements: tuple[str, ...]
    context_ids: tuple[str, ...]
    latency_ms: float
    reason: str | None = None
    exception_type: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class ReadOnlyScopedShadowObserver:
    """Observe scoped retrieval preparation without changing a candidate call."""

    def __init__(self, scoped_selector, preparation_shadow, *, clock=time.perf_counter, sink=None):
        self.scoped_selector = scoped_selector
        self.preparation_shadow = preparation_shadow
        self.clock = clock
        self.sink = sink
        self.records: list[ShadowObservation] = []

    def _record(self, observation: ShadowObservation) -> ShadowObservation:
        self.records.append(observation)
        if self.sink is not None:
            self.sink(observation.as_dict())
        return observation

    def observe(self, question: str) -> ShadowObservation:
        """Run only the experimental pre-answer path and always contain errors."""
        started = self.clock()
        digest = sha256(question.encode("utf-8")).hexdigest()
        try:
            scoped = self.scoped_selector.select(question)
            frozen_frontend = {
                "status": scoped.status,
                "active_subject": scoped.active_subject,
                "allowed_requirements": list(scoped.allowed_requirements),
                "selected_requirements": list(scoped.selection.selected_requirements) if scoped.selection else [],
                "reason": scoped.reason,
            }
            plan = self.preparation_shadow.prepare(question, frozen_frontend)
            return self._record(ShadowObservation(
                question_sha256=digest,
                status=plan.status,
                active_subject=plan.active_subject,
                selected_requirements=plan.selected_requirements,
                context_ids=tuple(item.chunk_id for item in plan.contexts),
                latency_ms=round((self.clock() - started) * 1000, 3),
                reason=plan.reason,
            ))
        except Exception as exc:  # Shadow must never affect the candidate request.
            return self._record(ShadowObservation(
                question_sha256=digest,
                status="shadow_exception",
                active_subject=None,
                selected_requirements=(),
                context_ids=(),
                latency_ms=round((self.clock() - started) * 1000, 3),
                reason="shadow_exception_isolated",
                exception_type=type(exc).__name__,
            ))
