"""P39-3C isolated scope/reference resolver and non-generative binder.

This prototype has no candidate-Agent, retrieval, or HCX dependency.  It
resolves subject identity/reference expressions only; it never creates a
direct requirement that the frozen selector did not return.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from src.experiments.direct_requirement_selector import DIRECT_REQUIREMENTS


_ACCOUNT_PATTERNS = (
    (re.compile(r"(?<![A-Za-z])DB(?![A-Za-z])", re.IGNORECASE), "DB"),
    (re.compile(r"(?<![A-Za-z])DC(?![A-Za-z])", re.IGNORECASE), "DC"),
    # These are entity aliases, not question-specific intent patterns.  Keep
    # DC's legal/expanded Korean name in the resolver so the scoped selector
    # can receive a single canonical account even when the acronym is absent.
    (re.compile(r"확정기여형(?:\s*퇴직연금(?:\s*제도)?)?"), "DC"),
    (re.compile(r"(?<![A-Za-z])IRP(?![A-Za-z])", re.IGNORECASE), "IRP"),
    (re.compile(r"연금저축"), "pension_savings"),
    (re.compile(r"ISA"), "ISA"),
)
_PRODUCT_CODE = re.compile(r"KR[A-Z0-9]{10}", re.IGNORECASE)
# A singular anaphora must never be expanded to every compatible antecedent.
# Keep the phrase-level detection broad across subject classes; the resolver
# below decides whether its preceding candidate set is uniquely identifiable.
_ANAPHORA = re.compile(r"(?P<expression>(?:그|이|해당)\s*(?:상품|계좌|제도|유형))")
_ORDINAL_LAST = re.compile(r"(?P<expression>후자|뒤에\s*(?:적은|말한)?\s*(?:상품|계좌|제도)?|두\s*번째\s*(?:상품|계좌|제도)?|마지막\s*(?:상품|계좌|제도)?)")
# Do not accept bare ``앞``: it occurs inside ordinary temporal wording such
# as ``앞으로도 고정인가요``.  An ordinal-first reference needs either the
# explicit ``전자``/``첫 번째`` form or a noun-bearing antecedent phrase.
_ORDINAL_FIRST = re.compile(r"(?P<expression>전자|앞(?:에)?\s*(?:적은|말한)\s*(?:상품|계좌|제도)?|앞의\s*(?:상품|계좌|제도|것)|첫\s*번째\s*(?:상품|계좌|제도)?)")
_CONTRAST = re.compile(r"(?P<subject>DB|DC)\s*(?:형)?\s*와\s*달리", re.IGNORECASE)
_OPERATION_PARTY_CUE = re.compile(r"(?:운용(?:방법|결정)?|적립금\s*선택).{0,16}(?:누가|누구)|(?:누가|누구).{0,16}(?:운용(?:방법|결정)?|고르)")
# ``without/excluding/only`` is a scope operator only when it links exactly
# two explicit candidate subjects.  A bare negative such as ``IRP가 아닌``
# must not silently choose the other entity.
_EXCLUSIVE_CONNECTOR = re.compile(
    r"(?:없이|제외(?:하고|한)?|빼고|말고|(?:사용|쓰|넣)(?:지)?\s*않(?:고|는)|(?:이|가)\s*(?:아닌|아니라))"
)
_ONLY_OR_STANDALONE = re.compile(r"^\s*(?:만(?=$|[\s,은는이가를에의])|단독(?:으로)?(?=$|[\s,은는이가를에의]))")
# ``B 말고 A도 가능한가`` asks whether A is an additional option.  It is
# not a request to exclude B, even though it uses an exclusion-like connector.
_ADDITIVE_AFTER_INCLUDED_SUBJECT = re.compile(r"^\s*(?:도|또한|역시)(?=$|[\s,은는이가를에의,.?!])")
_COMPARISON_CUE = re.compile(r"(?:비교|차이|각각|서로|대비)")


@dataclass(frozen=True)
class SubjectMention:
    subject: str
    order: int
    start: int
    end: int
    source: str


@dataclass(frozen=True)
class ReferenceResolution:
    expression: str
    kind: str
    resolved_to: tuple[str, ...]
    confidence: str
    excluded_subjects: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopeResolution:
    explicit_subjects: tuple[str, ...]
    subject_mentions: tuple[SubjectMention, ...]
    references: tuple[ReferenceResolution, ...]
    active_subjects: tuple[str, ...]
    unresolved_references: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "explicit_subjects": list(self.explicit_subjects),
            "subject_mentions": [asdict(item) for item in self.subject_mentions],
            "references": [
                {
                    "expression": item.expression,
                    "kind": item.kind,
                    "resolved_to": list(item.resolved_to),
                    "confidence": item.confidence,
                    "excluded_subjects": list(item.excluded_subjects),
                }
                for item in self.references
            ],
            "active_subjects": list(self.active_subjects),
            "unresolved_references": list(self.unresolved_references),
        }


@dataclass(frozen=True)
class RequirementBinding:
    subject: str | None
    requirement: str
    status: str


@dataclass(frozen=True)
class BindingResult:
    active_subjects: tuple[str, ...]
    bindings: tuple[RequirementBinding, ...]
    scope_conflicts: tuple[str, ...]
    unresolved_references: tuple[str, ...]
    incomplete_reasons: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "active_subjects": list(self.active_subjects),
            "bindings": [asdict(item) for item in self.bindings],
            "scope_conflicts": list(self.scope_conflicts),
            "unresolved_references": list(self.unresolved_references),
            "incomplete_reasons": list(self.incomplete_reasons),
        }


class ScopeReferenceResolver:
    """Resolve explicit and referential subjects without inferring requirements."""

    @staticmethod
    def _mentions(question: str) -> tuple[SubjectMention, ...]:
        found: list[SubjectMention] = []
        for pattern, canonical in _ACCOUNT_PATTERNS:
            for match in pattern.finditer(question):
                found.append(SubjectMention(canonical, 0, match.start(), match.end(), "explicit_account"))
        for match in _PRODUCT_CODE.finditer(question):
            found.append(SubjectMention(f"product:{match.group(0).upper()}", 0, match.start(), match.end(), "explicit_product_code"))
        ordered = sorted(found, key=lambda item: (item.start, item.end, item.subject))
        return tuple(SubjectMention(item.subject, index + 1, item.start, item.end, item.source) for index, item in enumerate(ordered))

    @staticmethod
    def _exclusive_scope(question: str, mentions: tuple[SubjectMention, ...], explicit: tuple[str, ...]) -> ReferenceResolution | None:
        """Resolve a narrowly expressed exclusion to its one included subject.

        Supported structural forms are ``B 없이 A만``, ``B 제외하고 A``
        and ``A 단독``.  This never treats a generic negative statement as an
        exclusive operator and never resolves three-or-more candidate scopes.
        """
        # Comparison wording retains all named subjects even if a negative
        # phrase occurs inside one side of the comparison.
        if _COMPARISON_CUE.search(question):
            return None
        if len(explicit) == 1:
            mention = next(item for item in mentions if item.subject == explicit[0])
            marker = _ONLY_OR_STANDALONE.match(question[mention.end:])
            if marker:
                return ReferenceResolution(marker.group(0).strip(), "exclusive_scope", explicit, "deterministic")
            return None
        if len(explicit) != 2:
            return None
        first, second = (next(item for item in mentions if item.subject == subject) for subject in explicit)
        left, right = (first, second) if first.start <= second.start else (second, first)
        between = question[left.end:right.start]
        connector = _EXCLUSIVE_CONNECTOR.search(between)
        if connector:
            # A connector is insufficient where the included subject is
            # explicitly additive (``B 말고 A도 가능한가``).  In that form,
            # treating B as excluded would silently drop a live alternative.
            if _ADDITIVE_AFTER_INCLUDED_SUBJECT.match(question[right.end:]):
                return None
            # ``B 제외하고 A`` unambiguously includes the subject after the
            # exclusion connector.  ``B 없이 A만`` is the same shape.
            return ReferenceResolution(
                connector.group(0), "exclusive_scope", (right.subject,), "deterministic", (left.subject,)
            )
        # Also permit the natural reversed wording ``A만, B 제외하고`` only
        # where the included entity carries an explicit only/standalone marker.
        marker = _ONLY_OR_STANDALONE.match(question[left.end:right.start])
        if marker and _EXCLUSIVE_CONNECTOR.search(question[right.end:]):
            return ReferenceResolution(
                marker.group(0).strip(), "exclusive_scope", (left.subject,), "deterministic", (right.subject,)
            )
        return None

    def resolve(self, question: str) -> ScopeResolution:
        mentions = self._mentions(question)
        explicit = tuple(dict.fromkeys(item.subject for item in mentions))
        references: list[ReferenceResolution] = []
        unresolved: list[str] = []
        active: tuple[str, ...] = explicit

        exclusive = self._exclusive_scope(question, mentions, explicit)
        if exclusive:
            references.append(exclusive)
            active = exclusive.resolved_to

        # A direct contrast in this closed two-system domain identifies the
        # complement, not a new factual requirement.
        contrast = _CONTRAST.search(question)
        if contrast:
            contrasted = contrast.group("subject").upper()
            complement = "DC" if contrasted == "DB" else "DB"
            references.append(ReferenceResolution(contrast.group(0), "closed_pair_contrast", (complement,), "inferred_closed_pair"))
            active = (complement,)

        products = tuple(item.subject for item in mentions if item.subject.startswith("product:"))
        ordinal_match = _ORDINAL_LAST.search(question) or _ORDINAL_FIRST.search(question)
        if ordinal_match:
            expression = ordinal_match.group("expression")
            if "상품" in expression:
                candidates, kind = products, "ordinal_product_reference"
            elif any(word in expression for word in ("계좌", "제도")):
                candidates, kind = tuple(item.subject for item in mentions if not item.subject.startswith("product:")), "ordinal_subject_reference"
            else:
                candidates, kind = products if len(products) >= 2 else explicit, "ordinal_subject_reference"
            if len(candidates) >= 2:
                target = candidates[-1] if _ORDINAL_LAST.search(question) else candidates[0]
                references.append(ReferenceResolution(expression, kind, (target,), "deterministic"))
                active = (target,)
            else:
                unresolved.append(expression)

        for match in _ANAPHORA.finditer(question):
            expression = match.group("expression")
            preceding = tuple(item.subject for item in mentions if item.end <= match.start())
            if "상품" in expression:
                candidates = tuple(subject for subject in preceding if subject.startswith("product:"))
            elif "계좌" in expression or "제도" in expression:
                candidates = tuple(subject for subject in preceding if not subject.startswith("product:"))
            else:
                # '그 유형' is not inherently tied to product, account, or
                # system scope.  It is only safe when exactly one antecedent
                # exists across the preceding context.
                candidates = preceding
            candidates = tuple(dict.fromkeys(candidates))
            if len(candidates) == 1:
                references.append(ReferenceResolution(expression, "nearest_anaphora", candidates, "deterministic"))
                active = candidates
            else:
                unresolved.append(expression)
        return ScopeResolution(explicit, mentions, tuple(references), active, tuple(dict.fromkeys(unresolved)))


class DeterministicBinder:
    """Bind only already-selected requirements; never fills a missing one."""

    _SUBJECT_PREFIXES = {
        "DB.": "DB", "DC.": "DC", "IRP.": "IRP", "pension_savings.": "pension_savings",
        "pension_savings_IRP.": None, "ISA.": "ISA", "retirement_income.IRP": "IRP",
    }

    @classmethod
    def _requirement_subject(cls, requirement: str) -> str | None:
        for prefix, subject in cls._SUBJECT_PREFIXES.items():
            if requirement.startswith(prefix):
                return subject
        return None

    @staticmethod
    def _selector_anchor(selected: tuple[str, ...]) -> tuple[str, ...]:
        subjects = []
        for requirement in selected:
            for prefix, subject in DeterministicBinder._SUBJECT_PREFIXES.items():
                if subject and requirement.startswith(prefix) and subject not in subjects:
                    subjects.append(subject)
        return tuple(subjects)

    def bind(self, question: str, resolution: ScopeResolution, selected_requirements: tuple[str, ...]) -> BindingResult:
        # Invalid selector output is rejected; no enum value is fabricated.
        unknown = tuple(value for value in selected_requirements if value not in DIRECT_REQUIREMENTS)
        if unknown:
            return BindingResult((), (), (f"unknown_requirement:{','.join(unknown)}",), resolution.unresolved_references, ())
        active = resolution.active_subjects
        unresolved = list(resolution.unresolved_references)
        anchors = self._selector_anchor(selected_requirements)
        if unresolved and not active and len(anchors) == 1:
            # A selected DC-scoped requirement can supply the antecedent for
            # '그 계좌'; it cannot supply a new missing requirement.
            active = anchors
            unresolved = []
        # When explicit candidates remain plural, an unresolved reference must
        # not silently turn into a broad comparison binding.  Preserve the
        # selector output but fail the binding closed.
        if unresolved:
            return BindingResult(
                active,
                tuple(RequirementBinding(None, requirement, "unresolved_reference") for requirement in selected_requirements),
                (),
                tuple(unresolved),
                (),
            )
        bindings, conflicts = [], []
        for requirement in selected_requirements:
            requirement_subject = self._requirement_subject(requirement)
            if requirement_subject and active and requirement_subject not in active:
                conflicts.append(f"subject_requirement_conflict:{requirement_subject}:{requirement}")
                bindings.append(RequirementBinding(requirement_subject, requirement, "conflict"))
            elif requirement.startswith("product."):
                products = tuple(subject for subject in active if subject.startswith("product:"))
                if len(products) == 1:
                    bindings.append(RequirementBinding(products[0], requirement, "bound"))
                elif products:
                    bindings.append(RequirementBinding("+".join(products), requirement, "bound_comparison"))
                else:
                    conflicts.append(f"product_subject_unresolved:{requirement}")
                    bindings.append(RequirementBinding(None, requirement, "unresolved"))
            else:
                bindings.append(RequirementBinding(requirement_subject, requirement, "bound"))
        incomplete = []
        if _OPERATION_PARTY_CUE.search(question) and not any(value.endswith(".operation_party") for value in selected_requirements):
            incomplete.append("selector_multi_requirement_incomplete:operation_party")
        return BindingResult(active, tuple(bindings), tuple(conflicts), tuple(unresolved), tuple(incomplete))
