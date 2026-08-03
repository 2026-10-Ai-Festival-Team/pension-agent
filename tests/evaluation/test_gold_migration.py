import pytest

from scripts.migrate_retrieval_gold import candidates_for_chunk
from src.models.chunk import ChunkLocator, ChunkType, SearchChunk


def chunk(chunk_id: str, source_id: str, element_ids: list[str]) -> SearchChunk:
    return SearchChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        source_path=f"{source_id}.pdf",
        source_format="pdf",
        document_type="pension_guide",
        chunk_type=ChunkType.PARAGRAPH_GROUP,
        text=chunk_id,
        locator=ChunkLocator(page_start=1, page_end=1),
        element_ids=element_ids,
    )


def test_gold_migration_returns_same_source_by_highest_element_overlap():
    old = chunk("old", "source-a", ["a", "b", "c"])
    candidates = candidates_for_chunk(
        old,
        [chunk("other-source", "source-b", ["a", "b", "c"]), chunk("partial", "source-a", ["a"]), chunk("best", "source-a", ["a", "b"])],
    )

    assert [candidate["new_chunk_id"] for candidate in candidates] == ["best", "partial"]
    assert candidates[0]["coverage"] == pytest.approx(2 / 3, abs=1e-6)
