import pytest

from src.experiments.p28_selective_workflow import (
    FrozenEvidenceBundle,
    WorkflowCitationBoundaryError,
    WorkflowVerifierPromptBuilder,
    WorkflowWriterPromptBuilder,
)
from src.models.document import AuthorityLevel, SourceType
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult

def _contexts():
    return [SearchResult(rank=1, chunk_id="chunk-1", source_id="source-1", source_path="x.pdf", source_format="pdf", document_type="guide", locator=ChunkLocator(page_start=1,page_end=1), element_ids=["e"], score=1, text="근거")]


def _mixed_contexts():
    return _contexts() + [
        SearchResult(
            rank=2,
            chunk_id="chunk-augmented",
            source_id="source-augmented",
            source_path="augmentation.json",
            source_format="pdf",
            document_type="guide",
            locator=ChunkLocator(page_start=2, page_end=2),
            element_ids=["aug"],
            score=0.5,
            text="보강 근거",
            source_type=SourceType.AUGMENTED,
            authority_level=AuthorityLevel.SECONDARY,
        )
    ]

def test_writer_keeps_requirement_and_citation_contract():
    payload = WorkflowWriterPromptBuilder(("DC 중도인출 사유",)).payload("질문", _contexts(), "HCX-007")
    text = payload["messages"][0]["content"]
    assert "DC 중도인출 사유" in text and "citation_id: chunk-1" in text and "source-1" not in text
    assert payload["responseFormat"]["type"] == "json"
    assert payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["items"]["enum"] == ["chunk-1"]

def test_verifier_uses_only_pass_or_revise_contract_and_given_evidence():
    builder = WorkflowVerifierPromptBuilder(("위험등급",), "답변")
    prompt = builder.build("질문", _contexts())
    assert "새 검색은 하지 말고" in prompt and "PASS" in prompt and "REVISE:" in prompt
    assert "citation_id: chunk-1" in prompt
    assert "새 evidence를 추가할 수 없습니다" in prompt
    payload = builder.payload("질문", _contexts(), "HCX-007")
    assert payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["items"]["enum"] == ["chunk-1"]


def test_frozen_bundle_rejects_selected_outside_or_augmented_citations():
    class Policy:
        def is_primary_original(self, item): return item.source_type == SourceType.ORIGINAL and item.authority_level == AuthorityLevel.PRIMARY
    bundle = FrozenEvidenceBundle.from_contexts(_mixed_contexts(), ("요구",), Policy())
    assert [item.chunk_id for item in bundle.contexts] == ["chunk-1"]
    assert bundle.allowed_primary_original_chunk_ids == ("chunk-1",)
    assert bundle.validates(["chunk-1"])
    # Writer와 Repair가 augmented ID 또는 selected context 밖 ID를 반환하면
    # 같은 frozen boundary에서 차단된다.
    assert not bundle.validates(["chunk-augmented"])
    assert not bundle.validates(["outside-primary"])
    assert not bundle.validates([])


def test_bundle_bound_schema_cannot_offer_augmented_or_unselected_citations():
    class Policy:
        def is_primary_original(self, item): return item.source_type == SourceType.ORIGINAL and item.authority_level == AuthorityLevel.PRIMARY

    bundle = FrozenEvidenceBundle.from_contexts(_mixed_contexts(), ("요구",), Policy())
    payload = WorkflowWriterPromptBuilder(bundle.requirements).payload("질문", list(bundle.contexts), "HCX-007")
    enum = payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["items"]["enum"]
    assert enum == ["chunk-1"]
    assert "chunk-augmented" not in payload["messages"][0]["content"]


def test_bundle_rejects_mismatched_context_and_allowed_ids():
    with pytest.raises(ValueError, match="context와 허용 citation ID"):
        FrozenEvidenceBundle(tuple(_contexts()), ("different-id",), ("요구",))


def test_boundary_error_keeps_stage_for_diagnostics():
    error = WorkflowCitationBoundaryError("Repair")
    assert error.stage == "Repair"
    assert "Repair citation" in str(error)
