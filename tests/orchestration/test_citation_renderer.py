from __future__ import annotations

import pytest

from src.generation.errors import CitationValidationError
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.citation_renderer import DocumentCitationRenderer
from src.orchestration.financial_answer_policy import FinancialAnswerPolicy
from src.orchestration.query_analyzer import QueryAnalyzer


def _context(chunk_id: str, *, page: int | None = 3, source_id: str = "ac97d050d2b39ec2", source_path: str = "투자설명서/KR510902511M/R2_KR510902511M.pdf"):
    return SearchResult(
        rank=1,
        chunk_id=chunk_id,
        score=1.0,
        text="원본 근거입니다.",
        source_id=source_id,
        source_path=source_path,
        source_format="pdf",
        document_type="pension_guide",
        locator=ChunkLocator(page_start=page, page_end=page),
        element_ids=[f"element-{chunk_id}"],
        metadata={},
    )


def test_host_renderer_uses_document_page_and_deduplicates_multiple_chunks():
    first = _context("internal-chunk-a")
    second = _context("internal-chunk-b")

    rendered = DocumentCitationRenderer().render([first, second])

    assert len(rendered) == 1
    assert rendered[0].display() == "- [DOC-7FB4C074DD06, p.3]"
    assert rendered[0].trace_dict()["chunk_ids"] == ["internal-chunk-a", "internal-chunk-b"]


def test_policy_rebuilds_model_citation_block_without_changing_answer_body():
    context = _context("7878a3be5806fef4-table-a3623398dbaa")
    policy = FinancialAnswerPolicy()
    answer = policy.format_answer(
        "원문의 세율 차이를 안내합니다.\n\n[근거]\n- [chunk_id: 7878a3be5806fef4-table-a3623398dbaa]",
        QueryAnalyzer().analyze("퇴직소득세 차이를 알려주세요."),
        [context],
    )

    assert "원문의 세율 차이를 안내합니다." in answer
    assert "[DOC-7FB4C074DD06, p.3]" in answer
    assert "7878a3be5806fef4-table-a3623398dbaa" not in answer


def test_unknown_source_provenance_is_a_strict_citation_failure():
    with pytest.raises(CitationValidationError) as error:
        DocumentCitationRenderer().render([_context("unmapped", source_id="unmapped", source_path="docs_renamed/unknown.pdf")])

    assert error.value.diagnostic["citation_validation_reason"] == "citation_provenance_source_unknown"


def test_registry_rejects_source_path_mismatch():
    context = _context("verified-chunk")
    context = context.model_copy(update={"source_id": "ac97d050d2b39ec2", "source_path": "wrong.pdf"})

    with pytest.raises(CitationValidationError) as error:
        DocumentCitationRenderer().render([context])

    assert error.value.diagnostic["citation_validation_reason"] == "citation_provenance_mismatch"


def test_filename_locator_fallback_is_allowed_without_a_doc_id():
    rendered = DocumentCitationRenderer().render([
        _context(
            "fallback-chunk",
            page=1,
            source_id="0235557ce8059551",
            source_path="투자설명서/KR5125450070/R2_KR5125450070.pdf",
        )
    ])

    assert rendered[0].display() == "- [R2_KR5125450070.pdf, p.1]"
    assert rendered[0].trace_dict()["citation_scope"] == "document_location"
    assert rendered[0].trace_dict()["document_id"] is None


def test_document_level_fallback_is_allowed_when_source_has_no_locator():
    rendered = DocumentCitationRenderer().render([
        _context(
            "document-fallback-chunk",
            page=None,
            source_id="04782a392f49293e",
            source_path="docs_renamed/doc55.docx",
        )
    ])

    assert rendered[0].display() == "- [doc55.docx]"
    assert rendered[0].trace_dict()["citation_scope"] == "document"
    assert "locator" not in rendered[0].trace_dict()


def test_raw_chunk_id_in_answer_body_is_not_allowed_to_reach_a_user():
    context = _context("internal-chunk-only")

    with pytest.raises(CitationValidationError) as error:
        FinancialAnswerPolicy().format_answer(
            "답변 본문에 internal-chunk-only를 쓰면 안 됩니다.",
            QueryAnalyzer().analyze("제도 차이를 알려주세요."),
            [context],
        )

    assert error.value.diagnostic["citation_validation_reason"] == "user_facing_internal_id"


def test_raw_source_id_in_answer_body_is_not_allowed_to_reach_a_user():
    context = _context("internal-chunk-only")

    with pytest.raises(CitationValidationError) as error:
        FinancialAnswerPolicy().format_answer(
            "답변 본문에 ac97d050d2b39ec2를 쓰면 안 됩니다.",
            QueryAnalyzer().analyze("제도 차이를 알려주세요."),
            [context],
        )

    assert error.value.diagnostic["citation_validation_reason"] == "user_facing_internal_id"
