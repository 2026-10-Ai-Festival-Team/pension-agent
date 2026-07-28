import pytest
from pydantic import ValidationError

from src.models.chunk import ChunkLocator, ChunkType, SearchChunk


def make_chunk() -> SearchChunk:
    return SearchChunk(
        chunk_id="source-1-p2-c1",
        source_id="source-1",
        source_path="docs/sample.pdf",
        source_format="pdf",
        document_type="pension_guide",
        chunk_type=ChunkType.PARAGRAPH_GROUP,
        text="원문 기반 청크입니다.",
        locator=ChunkLocator(page_start=2, page_end=2),
        element_ids=["source-1-p2-b0"],
    )


def test_chunk_serializes_with_source_traceability() -> None:
    chunk = make_chunk()

    assert chunk.source_id == "source-1"
    assert chunk.locator.page_start == 2
    assert chunk.element_ids == ["source-1-p2-b0"]
    assert '"chunk_id":"source-1-p2-c1"' in chunk.model_dump_json()


def test_chunk_requires_non_empty_source_elements() -> None:
    payload = make_chunk().model_dump()
    payload["element_ids"] = []

    with pytest.raises(ValidationError):
        SearchChunk(**payload)


def test_chunk_rejects_duplicate_source_elements() -> None:
    payload = make_chunk().model_dump()
    payload["element_ids"] = ["source-1-p2-b0", "source-1-p2-b0"]

    with pytest.raises(ValidationError):
        SearchChunk(**payload)


def test_locator_rejects_inverted_page_range() -> None:
    with pytest.raises(ValidationError):
        ChunkLocator(page_start=3, page_end=2)
