"""Isolated resolver-first, subject-filtered direct-selector experiment."""
from __future__ import annotations

from dataclasses import dataclass

from src.experiments.direct_requirement_selector import requirements_for_active_subject
from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver


@dataclass(frozen=True)
class ScopedSelectionResult:
    status: str
    active_subject: str | None
    allowed_requirements: tuple[str, ...]
    selection: object | None
    resolution: object
    binding: object | None
    reason: str | None


class ResolverFirstScopedSelector:
    """Call a selector only when deterministic scope has exactly one subject.

    This wrapper never derives a requirement.  Plural or unresolved scope is
    terminal for this single-subject experiment; it is intentionally not a
    generic comparison handler.
    """

    def __init__(self, selector, resolver=None, binder=None):
        self.selector = selector
        self.resolver = resolver or ScopeReferenceResolver()
        self.binder = binder or DeterministicBinder()

    def select(self, question: str) -> ScopedSelectionResult:
        resolution = self.resolver.resolve(question)
        if resolution.unresolved_references or len(resolution.active_subjects) != 1:
            return ScopedSelectionResult(
                status="unresolved_scope",
                active_subject=None,
                allowed_requirements=(),
                selection=None,
                resolution=resolution,
                binding=None,
                reason="unresolved_reference" if resolution.unresolved_references else "non_unique_active_subject",
            )
        active = resolution.active_subjects[0]
        allowed = requirements_for_active_subject(active)
        selection = self.selector.select(question, allowed_requirements=allowed, active_subjects=(active,))
        binding = self.binder.bind(question, resolution, selection.selected_requirements)
        return ScopedSelectionResult(
            status="selected" if selection.schema_valid and selection.ontology_valid else "selector_contract_error",
            active_subject=active,
            allowed_requirements=allowed,
            selection=selection,
            resolution=resolution,
            binding=binding,
            reason=None,
        )
