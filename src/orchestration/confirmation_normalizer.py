"""Separate a Korean factual proposition from confirmation-style modality.

The resolver must continue to receive the original question because phrases
such as ``IRP 말고 연금저축만`` genuinely change subject scope.  This module
only removes *terminal epistemic modality* for factual selection, for example
``맞지? 아닌가?``.  It never turns a scope exclusion into a confirmation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re


_OPERATION_CUE = re.compile(r"(?:운용|굴리|관리|맡)")
_SELF_DOUBT = re.compile(r"(?:잘못\s*알고|착각|모르겠|인\s*줄\s*알았는데|아닌가|아니었나)")
_CORRECTION_SEEKING = re.compile(r"(?:잘못\s*알고\s*있으면\s*알려|아니라면\s*정정|맞는지\s*확인)")
_HEDGED = re.compile(r"(?:제\s*기억엔|제가\s*알기로는|아마)")
# This pattern is anchored to the final utterance.  It therefore does not
# touch ``IRP 말고 연금저축만`` or any in-sentence scope connector.
_TERMINAL_MODALITY = re.compile(
    r"(?:"
    r"맞(?:지|죠|나|나요|아|아요)|맞는\s*(?:거|것)(?:지|죠)|"
    r"그런\s*(?:거|것)(?:야|지|죠)|그런가|"
    r"(?:거|것)\s*(?:아니야|아닌가요?|아니었(?:어|나요)?|아니지)|"
    r"아닌가요?|아니었나요?|아닌가|아니었나|"
    r"맞는지\s*모르겠(?:는데|어요|다)?"
    r")\s*[?!.…。]*$"
)
_HEDGE_PREFIX = re.compile(r"^\s*(?:제\s*기억엔|제가\s*알기로는|아마)\s*")
_CORRECTION_SUFFIX = re.compile(r"\s*(?:내가|제가)\s*(?:잘못\s*알고|착각)\s*있(?:는)?(?:가|나요)?\s*[?!.…。]*$")


@dataclass(frozen=True)
class ConfirmationNormalization:
    original_question: str
    proposition_core: str
    query_modality: str  # neutral | confirmation | confirmation_uncertain | correction_seeking
    changed: bool

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_confirmation_query(question: str) -> ConfirmationNormalization:
    """Return a selector-safe factual core while retaining the original input.

    The output is intentionally conservative: only an end-of-question
    confirmation/self-doubt expression or a hedged prefix is stripped.  A
    core that becomes empty falls back to the original question.
    """
    original = " ".join(question.strip().split())
    core = _HEDGE_PREFIX.sub("", original)
    changed = core != original
    stripped_terminal = False
    # ``맞지? 아닌가?`` contains two terminal modalities.  Remove both while
    # preserving the factual predicate before them.
    for _ in range(3):
        match = _TERMINAL_MODALITY.search(core)
        if not match:
            break
        candidate = core[:match.start()].rstrip(" ,;:?-–")
        if not candidate:
            break
        core, changed, stripped_terminal = candidate, True, True
    correction = _CORRECTION_SUFFIX.search(core)
    if correction:
        candidate = core[:correction.start()].rstrip(" ,;:?-–")
        if candidate:
            core, changed, stripped_terminal = candidate, True, True

    if _CORRECTION_SEEKING.search(original):
        modality = "correction_seeking"
    elif _SELF_DOUBT.search(original):
        modality = "confirmation_uncertain"
    elif stripped_terminal or _HEDGED.search(original):
        modality = "confirmation"
    else:
        modality = "neutral"
    return ConfirmationNormalization(original, core or original, modality, changed)


def confirmation_core_requirements(
    normalization: ConfirmationNormalization,
    *,
    active_subjects: tuple[str, ...],
    allowed_requirements: tuple[str, ...],
) -> tuple[str, ...]:
    """Return the narrow deterministic requirement implied by an operation core.

    This is a selector-side semantic rule, never a Binder repair.  It applies
    only after a unique DB/DC subject has already been resolved and only where
    the factual predicate explicitly asks who operates/manages the reserves.
    """
    if len(active_subjects) != 1 or active_subjects[0] not in {"DB", "DC"}:
        return ()
    if not _OPERATION_CUE.search(normalization.proposition_core):
        return ()
    requirement = f"{active_subjects[0]}.operation_party"
    return (requirement,) if requirement in allowed_requirements else ()
