import json
from pathlib import Path

import pytest

from src.config.generation import GenerationSettings
from src.generation.hcx import HyperClovaXGenerator
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResponse, SearchResult
from src.orchestration.agent import PensionAgent


FIXTURES = Path(__file__).parents[1] / "fixtures" / "hcx_citation_cases"


class FixtureTransport:
    def __init__(self, fixture_name):
        self.body = (FIXTURES / fixture_name).read_text(encoding="utf-8")

    def post(self, *_):
        return 200, self.body


class FixtureRetriever:
    def __init__(self, chunk_ids):
        self.results = [
            SearchResult(
                rank=index + 1,
                chunk_id=chunk_id,
                source_id=f"source-{index}",
                source_path="fixture.pdf",
                source_format="pdf",
                document_type="pension_guide",
                locator=ChunkLocator(page_start=1, page_end=1),
                element_ids=[f"element-{index}"],
                score=1.0,
                text="검증 근거",
                metadata={"document_id": "DOC-TEST00000004"},
            )
            for index, chunk_id in enumerate(chunk_ids)
        ]

    def search(self, query, top_k=5):
        return SearchResponse(query=query, tokenizer="fixture", total_candidates=len(self.results), results=self.results)


def generator(fixture_name):
    config = GenerationSettings(
        generator_backend="hcx",
        hcx_api_key="secret",
        hcx_model="HCX-DASH-002",
        hcx_base_url="https://example.invalid",
        max_retries=0,
        hcx_min_interval_seconds=0,
    )
    return HyperClovaXGenerator(config=config, transport=FixtureTransport(fixture_name))


def answer_for(fixture_name, chunk_ids):
    return PensionAgent(FixtureRetriever(chunk_ids), generator(fixture_name)).answer("DB형 운용 주체는?")


def test_valid_and_multiple_allowed_citations_pass():
    result = answer_for("valid_citation.json", ["allowed-chunk-001", "allowed-chunk-002"])

    assert result["think_trace"]["generator_called"] is True
    assert result["think_trace"]["cited_chunk_ids"] == ["allowed-chunk-001", "allowed-chunk-002"]


@pytest.mark.parametrize(
    ("fixture_name", "chunk_ids", "returned_ids"),
    [
        ("r009_wrong_identifier_type.json", ["7878a3be5806fef4-paragraph_group-d24f4b2854ed"], ["7878a3be5806fef4"]),
        (
            "r012_wrong_identifier_type.json",
            [
                "4ae16261de11da35-table-bdf681407cec",
                "4ae16261de11da35-table-cae3223cb315",
                "1bfc399c9b3d6a67-table-c9ca47302c31",
            ],
            ["4ae16261de11da35", "1bfc399c9b3d6a67"],
        ),
        ("whitespace_variation.json", ["allowed-chunk-001"], [" allowed-chunk-001 "]),
    ],
)
def test_noncanonical_or_wrong_identifier_is_not_inferred(fixture_name, chunk_ids, returned_ids):
    result = answer_for(fixture_name, chunk_ids)
    diagnostic = result["think_trace"]["generation_diagnostic"]

    assert result["think_trace"]["generator_called"] is False
    assert diagnostic["citation_validation_reason"] == "unknown_chunk_id"
    assert diagnostic["returned_cited_chunk_ids"] == returned_ids


@pytest.mark.parametrize("fixture_name", ["missing_citation_field.json", "r035_empty_citation.json"])
def test_missing_or_empty_citation_is_rejected(fixture_name):
    result = answer_for(fixture_name, ["allowed-chunk-001"])
    diagnostic = result["think_trace"]["generation_diagnostic"]

    assert result["think_trace"]["generator_called"] is False
    assert diagnostic["citation_validation_reason"] == "missing_citation"
    assert diagnostic["returned_cited_chunk_ids"] == []


def test_missing_citation_fixture_keeps_parser_presence_diagnostic():
    result = answer_for("missing_citation_field.json", ["allowed-chunk-001"])

    assert result["think_trace"]["generation_diagnostic"]["cited_chunk_ids_present"] is False
