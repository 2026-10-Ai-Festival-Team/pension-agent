from src.experiments.multi_evidence import (
    CitationBindingPromptBuilder,
    RequirementAwarePromptBuilder,
    RequirementCase,
    RequirementEvidenceSelector,
    RequirementSlot,
)
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult


def result(rank, chunk_id, text, score=1.0):
    return SearchResult(
        rank=rank, chunk_id=chunk_id, score=score, text=text, source_id="source",
        source_path="guide.pdf", source_format="pdf", document_type="guide",
        locator=ChunkLocator(page_start=rank, page_end=rank), element_ids=[chunk_id],
    )


def test_selector_uses_only_top_k_and_keeps_one_context_per_requirement():
    case = RequirementCase(
        "R-002", "target", (
            RequirementSlot("DB 산정", ("DB", "평균임금"), 2),
            RequirementSlot("DC 산정", ("DC", "부담금", "운용손익"), 2),
        ),
    )
    selection = RequirementEvidenceSelector().select(case, [
        result(1, "distractor", "DB와 DC를 비교합니다."),
        result(2, "db", "DB 퇴직급여는 평균임금으로 계산합니다."),
        result(7, "dc", "DC 부담금 누계액과 운용손익으로 급여가 결정됩니다."),
    ])

    assert selection.complete
    assert [item.chunk_id for item in selection.contexts] == ["db", "dc"]
    assert [match.result.chunk_id for match in selection.matches] == ["db", "dc"]


def test_selector_is_fail_closed_when_a_requirement_has_no_match():
    case = RequirementCase("R-024", "audit", (RequirementSlot("위험등급", ("위험등급",), 1),))
    selection = RequirementEvidenceSelector().select(case, [result(1, "generic", "상품 가격은 변동할 수 있습니다.")])

    assert not selection.complete
    assert selection.contexts == ()
    assert selection.missing_slot_names == ["위험등급"]


def test_prompt_binds_each_requirement_to_only_selected_chunk_ids():
    case = RequirementCase("R-011", "target", (RequirementSlot("과세 시점", ("과세이연",), 1),))
    evidence = result(7, "tax-table", "IRP는 과세이연 후 연금수령 시 과세합니다.")
    selection = RequirementEvidenceSelector().select(case, [evidence])

    prompt = RequirementAwarePromptBuilder(selection).build("질문", list(selection.contexts))

    assert "[질문 요구 항목]" in prompt
    assert "과세 시점: tax-table" in prompt
    assert "허용 chunk_id" in prompt


def test_selector_matches_table_phrases_split_by_pdf_line_breaks():
    case = RequirementCase("R-002", "target", (RequirementSlot("DC 산정", ("DC", "부담금", "운용 손익"), 3),))
    selection = RequirementEvidenceSelector().select(
        case, [result(10, "dc-table", "DC 퇴직급여는 부담금 누계액 ± 운용\n손익입니다.")]
    )

    assert selection.complete
    assert selection.contexts[0].chunk_id == "dc-table"


def test_citation_binding_prompt_exposes_no_source_id_and_only_citation_id():
    case = RequirementCase("R-011", "target", (RequirementSlot("과세 시점", ("과세이연",), 1),))
    evidence = SearchResult(
        rank=1, chunk_id="full-chunk-id", source_id="hidden-source-id", source_path="tax.pdf",
        source_format="pdf", document_type="guide", locator=ChunkLocator(page_start=7, page_end=7),
        element_ids=["e"], score=1.0, text="과세이연 후 연금 수령 시 과세합니다.",
    )
    selection = RequirementEvidenceSelector().select(case, [evidence])

    prompt = CitationBindingPromptBuilder(selection).build("질문", list(selection.contexts))

    assert "citation_id: full-chunk-id" in prompt
    assert "hidden-source-id" not in prompt
    assert "source_id" in prompt  # It is named only as a prohibited identifier.
