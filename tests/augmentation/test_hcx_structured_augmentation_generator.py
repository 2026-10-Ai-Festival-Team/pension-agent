from __future__ import annotations

import json

import pytest

from src.augmentation.candidate_builder import build_candidate
from src.augmentation.candidate_schema import GeneratedAugmentationText, HostOwnedAugmentationRequest
from src.augmentation.hcx_structured_generator import HCXStructuredAugmentationGenerator
from src.config.generation import GenerationSettings


class Transport:
    def __init__(self, content: dict):
        self.body = json.dumps({"result": {"message": {"content": json.dumps(content, ensure_ascii=False)}}})

    def post(self, *_args):
        return 200, self.body


def config(model: str = "HCX-007") -> GenerationSettings:
    return GenerationSettings(generator_backend="hcx", hcx_api_key="test", hcx_model=model, hcx_base_url="https://example", max_retries=0, hcx_min_interval_seconds=0)


def test_augmentation_structured_caller_is_hcx007_only_and_uses_explicit_non_reasoning_mode() -> None:
    with pytest.raises(ValueError):
        HCXStructuredAugmentationGenerator(config=config("HCX-005"))
    caller = HCXStructuredAugmentationGenerator(config=config(), transport=Transport({"question": "DB는 누가 운용하나요?", "answer": "회사가 운용합니다.", "coverage_tags": ["natural"], "augmentation_type": "natural_language_variation"}))
    payload = caller.payload("evidence-only prompt")
    assert payload["responseFormat"]["type"] == "json"
    assert payload["responseFormat"]["schema"]["required"] == ["question", "answer", "coverage_tags", "augmentation_type"]
    assert payload["thinking"] == {"effort": "none"}
    assert caller.generate("evidence-only prompt").answer == "회사가 운용합니다."


def test_candidate_builder_keeps_outcome_and_provenance_host_owned() -> None:
    host = HostOwnedAugmentationRequest(
        candidate_id="P49-2H-2-0001", coverage_cell="D17-Q08-bounded", target_outcome="bounded_answer",
        evidence_chunk_ids=("chunk-123",), source_ids=("doc-17",), source_seed_id=None,
        generation_prompt_version="p49-2h-2-v1", allowed_coverage_tags=("future_limit",),
        allowed_augmentation_types=("natural_language_variation",),
    )
    generated = GeneratedAugmentationText("이 상품 위험등급은 어떻게 바뀔 수 있나요?", "현재 자료에는 변경 가능성만 있습니다.", ("future_limit",), "natural_language_variation")
    candidate = build_candidate(host, generated)
    assert candidate["outcome"] == "bounded_answer"
    assert candidate["evidence_chunk_ids"] == ["chunk-123"]
    assert candidate["source_ids"] == ["doc-17"]
    assert candidate["generation_model"] == "HCX-007"
    assert candidate["candidate_lifecycle"]["state"] == "generated"
    assert candidate["acceptance_status"] == "not_accepted"


def test_candidate_builder_rejects_model_labels_outside_host_allowlist() -> None:
    host = HostOwnedAugmentationRequest(
        candidate_id="P49-2H-2-0002", coverage_cell="D17-Q08-bounded", target_outcome="bounded_answer",
        evidence_chunk_ids=("chunk-123",), source_ids=("doc-17",), source_seed_id=None,
        generation_prompt_version="p49-2h-2-v1", allowed_coverage_tags=("future_limit",),
        allowed_augmentation_types=("natural_language_variation",),
    )
    generated = GeneratedAugmentationText("질문", "답", ("unapproved_tag",), "natural_language_variation")
    with pytest.raises(ValueError, match="allowlist"):
        build_candidate(host, generated)


def test_generated_text_rejects_hcx_attempt_to_claim_host_authority() -> None:
    with pytest.raises(ValueError, match="unexpected authority"):
        GeneratedAugmentationText.from_mapping({"question": "질문", "answer": "답", "coverage_tags": [], "augmentation_type": "x", "outcome": "supported_answer"})
