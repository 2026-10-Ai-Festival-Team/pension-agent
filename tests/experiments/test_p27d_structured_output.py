from src.experiments.citation_diagnosis import NativeStructuredCitationPromptBuilder
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult


class _Selection:
    matches = ()


def test_native_structured_citation_builder_keeps_minimal_citation_representation():
    contexts = [
        SearchResult(
            rank=1,
            chunk_id="chunk-001",
            source_id="source-001",
            source_path="guide.pdf",
            source_format="pdf",
            document_type="guide",
            locator=ChunkLocator(page_start=1, page_end=1),
            element_ids=["element-001"],
            score=1.0,
            text="근거",
        )
    ]
    builder = NativeStructuredCitationPromptBuilder("B_minimal_no_other_identifier", _Selection())

    payload = builder.payload("질문", contexts, "HCX-007")

    assert "citation_id: chunk-001" in payload["messages"][0]["content"]
    assert "source-001" not in payload["messages"][0]["content"]
    assert payload["thinking"] == {"effort": "none"}
    assert payload["responseFormat"]["type"] == "json"
