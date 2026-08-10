from src.experiments.citation_diagnosis import CitationDiagnosisPromptBuilder, prompt_identifier_exposure
from src.experiments.multi_evidence import RequirementCase, RequirementEvidenceSelector, RequirementSlot
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult


def selection():
    context = SearchResult(
        rank=1, chunk_id="source-123-table-456", source_id="source-123", source_path="fund.pdf",
        source_format="pdf", document_type="fund", locator=ChunkLocator(page_start=2, page_end=2),
        element_ids=["e"], score=1.0, text="국내 주식에 투자합니다.",
    )
    case = RequirementCase("R-028", "target", (RequirementSlot("투자대상", ("국내 주식",), 1),))
    return RequirementEvidenceSelector().select(case, [context])


def test_minimal_variant_does_not_expose_actual_source_id_value():
    value = selection()
    prompt = CitationDiagnosisPromptBuilder("B_minimal_no_other_identifier", value).build("질문", list(value.contexts))
    exposure = prompt_identifier_exposure(prompt, value.contexts)

    assert not exposure["source_id_exposed_separately"]
    assert not exposure["literal_source_id_label_present"]
    assert exposure["all_chunk_ids_present"]


def test_whitelist_variant_repeats_the_full_allowed_chunk_id():
    value = selection()
    prompt = CitationDiagnosisPromptBuilder("D_explicit_json_whitelist", value).build("질문", list(value.contexts))

    assert prompt.count("source-123-table-456") >= 2
