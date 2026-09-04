"""Authority-separated schemas for P49-2H augmentation candidates."""
from __future__ import annotations

from dataclasses import dataclass


OUTCOMES = frozenset({"supported_answer", "clarification_required", "bounded_answer"})


@dataclass(frozen=True)
class HostOwnedAugmentationRequest:
    candidate_id: str
    coverage_cell: str
    target_outcome: str
    evidence_chunk_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_seed_id: str | None
    generation_prompt_version: str
    allowed_coverage_tags: tuple[str, ...] = ()
    allowed_augmentation_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.coverage_cell:
            raise ValueError("candidate_id and coverage_cell are required")
        if self.target_outcome not in OUTCOMES:
            raise ValueError("target_outcome is not canonical")
        if self.target_outcome == "supported_answer" and not self.evidence_chunk_ids:
            raise ValueError("supported_answer requires host-bound evidence")
        if len(self.evidence_chunk_ids) != len(set(self.evidence_chunk_ids)):
            raise ValueError("evidence_chunk_ids must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("source_ids must be unique")


@dataclass(frozen=True)
class GeneratedAugmentationText:
    """Only the four natural-language fields HCX is allowed to own."""

    question: str
    answer: str
    coverage_tags: tuple[str, ...]
    augmentation_type: str

    @classmethod
    def from_mapping(cls, payload: object) -> "GeneratedAugmentationText":
        if not isinstance(payload, dict):
            raise ValueError("structured augmentation response must be an object")
        required = {"question", "answer", "coverage_tags", "augmentation_type"}
        if set(payload) != required:
            raise ValueError("structured augmentation response has unexpected authority fields")
        if not isinstance(payload["question"], str) or not payload["question"].strip():
            raise ValueError("question must be a non-empty string")
        if not isinstance(payload["answer"], str) or not payload["answer"].strip():
            raise ValueError("answer must be a non-empty string")
        if not isinstance(payload["coverage_tags"], list) or not all(isinstance(tag, str) and tag for tag in payload["coverage_tags"]):
            raise ValueError("coverage_tags must be a non-empty-string array")
        if not isinstance(payload["augmentation_type"], str) or not payload["augmentation_type"].strip():
            raise ValueError("augmentation_type must be a non-empty string")
        return cls(payload["question"].strip(), payload["answer"].strip(), tuple(payload["coverage_tags"]), payload["augmentation_type"].strip())

    def validate_against(self, host: HostOwnedAugmentationRequest) -> None:
        """Reject model labels outside the host's coverage contract."""
        if not host.allowed_coverage_tags or not set(self.coverage_tags).issubset(host.allowed_coverage_tags):
            raise ValueError("coverage_tags are outside the host allowlist")
        if not host.allowed_augmentation_types or self.augmentation_type not in host.allowed_augmentation_types:
            raise ValueError("augmentation_type is outside the host allowlist")
