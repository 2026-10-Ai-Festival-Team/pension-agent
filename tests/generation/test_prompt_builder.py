import pytest

from src.generation.prompt_builder import NativeStructuredOutputPromptBuilder, PromptBuilder
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult


def test_prompt_lists_only_context_chunk_ids_as_allowed_citations():
    context = [
        SearchResult(
            rank=1,
            chunk_id="chunk-001",
            source_id="source-001",
            source_path="guide.pdf",
            source_format="pdf",
            document_type="pension_guide",
            locator=ChunkLocator(page_start=1, page_end=1),
            element_ids=["element-001"],
            score=1.0,
            text="근거",
        )
    ]

    prompt = PromptBuilder().build("질문", context)

    assert "[허용 chunk_id]" in prompt
    assert "chunk-001" in prompt
    assert "source_id" in prompt
    assert "빈 배열은 허용되지 않습니다" in prompt


def test_hcx_v3_payload_uses_camel_case_max_tokens():
    payload = PromptBuilder().payload("질문", [], "HCX-DASH-002")

    assert payload["maxTokens"] == 800
    assert "max_tokens" not in payload


def test_hcx_007_uses_the_inference_request_contract():
    payload = PromptBuilder().payload("질문", [], "HCX-007")

    assert payload["maxCompletionTokens"] == 800
    assert "maxTokens" not in payload
    assert payload["thinking"] == {"effort": "none"}
    assert payload["messages"][0]["content"] == [{"type": "text", "text": payload["messages"][0]["content"][0]["text"]}]


def test_native_structured_output_payload_uses_hcx007_schema_with_thinking_disabled():
    payload = NativeStructuredOutputPromptBuilder().payload("질문", [], "HCX-007")

    assert payload["messages"][0]["content"] == NativeStructuredOutputPromptBuilder().build("질문", [])
    assert payload["thinking"] == {"effort": "none"}
    assert payload["maxCompletionTokens"] == 800
    assert payload["responseFormat"]["type"] == "json"
    assert payload["responseFormat"]["schema"]["required"] == ["answer", "cited_chunk_ids"]
    assert payload["responseFormat"]["schema"]["properties"]["cited_chunk_ids"]["minItems"] == 1


def test_native_structured_output_rejects_non_hcx007_model():
    with pytest.raises(ValueError, match="HCX-007"):
        NativeStructuredOutputPromptBuilder().payload("질문", [], "HCX-DASH-002")
