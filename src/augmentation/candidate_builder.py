"""Host-owned final candidate assembly for offline P49 augmentation."""
from __future__ import annotations

from src.augmentation.candidate_schema import GeneratedAugmentationText, HostOwnedAugmentationRequest


def build_candidate(host: HostOwnedAugmentationRequest, generated: GeneratedAugmentationText) -> dict:
    """Attach immutable host provenance after structured HCX generation.

    ``generated`` deliberately cannot carry outcome, source, quota, seed, or
    candidate identity. The resulting object remains a draft: it cannot be
    interpreted as human-approved or training-exportable.
    """
    generated.validate_against(host)
    return {
        "candidate_id": host.candidate_id,
        "question": generated.question,
        "answer": generated.answer,
        "outcome": host.target_outcome,
        "coverage_cell": host.coverage_cell,
        "coverage_tags": list(generated.coverage_tags),
        "augmentation_type": generated.augmentation_type,
        "evidence_chunk_ids": list(host.evidence_chunk_ids),
        "source_ids": list(host.source_ids),
        "source_seed_id": host.source_seed_id,
        "generation_model": "HCX-007",
        "generation_prompt_version": host.generation_prompt_version,
        "generation_attempt": 1,
        "generation_parameters": {"temperature": 0, "topP": None, "maxTokens": 1200},
        "generation_status": "generated",
        "validation_status": "pending",
        "validation_failures": [],
        "human_review_status": "pending",
        "acceptance_status": "not_accepted",
        "candidate_lifecycle": {
            "state": "generated",
            "schema": "pending",
            "evidence": "pending",
            "semantic": "pending",
            "dedup": "pending",
            "human_review": "pending",
            "acceptance": "not_accepted",
        },
        "training_export_allowed": False,
    }
