from src.generation.prompt_builder import PromptBuilder
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
    assert "허용 목록 밖의 ID" in prompt


def test_hcx_v3_payload_uses_camel_case_max_tokens():
    payload = PromptBuilder().payload("질문", [], "HCX-DASH-002")

    assert payload["maxTokens"] == 800
    assert "max_tokens" not in payload
