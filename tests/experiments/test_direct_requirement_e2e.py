from src.experiments.direct_requirement_e2e import DirectRequirementE2EAgent
from src.experiments.direct_requirement_selector import DirectRequirementSelection
from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver
from src.experiments.scoped_direct_requirement_selector import ScopedSelectionResult
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.generation.fake import FakeGenerator
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResponse, SearchResult


class _Retriever:
    def search(self, query, top_k):
        return SearchResponse(
            query=query, tokenizer="simple", total_candidates=1,
            results=[SearchResult(
                rank=1, chunk_id="primary-1", score=1.0, text="DC형 적립금 운용 주체는 근로자입니다.",
                source_id="source-1", source_path="guide.pdf", source_format="pdf", document_type="guide",
                locator=ChunkLocator(page_start=1, page_end=1), source_type=SourceType.ORIGINAL,
                authority_level=AuthorityLevel.PRIMARY,
            )],
        )


def _selected(question="DC형 적립금 운용 주체"):
    requirement = "DC.operation_party"
    resolver = ScopeReferenceResolver()
    resolution = resolver.resolve(question)
    selection = DirectRequirementSelection(
        (requirement,), (), False, True, True, (), {"source": "test"},
    )
    return ScopedSelectionResult(
        "selected", "DC", (requirement,), selection, resolution,
        DeterministicBinder().bind(question, resolution, selection.selected_requirements), None,
    )


class _Selector:
    def select(self, question):
        return _selected(question)


class _UnresolvedSelector:
    def select(self, question):
        resolver = ScopeReferenceResolver()
        resolution = resolver.resolve(question)
        return ScopedSelectionResult("unresolved_scope", None, (), None, resolution, None, "non_unique_active_subject")


class _CapturingPreparation(ScopedFrontendPreparationShadow):
    def __init__(self):
        super().__init__(_Retriever())
        self.frontend_payload = None

    def prepare(self, question, frozen_frontend):
        self.frontend_payload = frozen_frontend
        return super().prepare(question, frozen_frontend)


def test_e2e_uses_only_scoped_prepared_primary_context_for_generation():
    agent = DirectRequirementE2EAgent(
        _Selector(), ScopedFrontendPreparationShadow(_Retriever()), FakeGenerator(),
    )
    response = agent.answer("DC형 적립금은 누가 운용하나요?")

    assert response["think_trace"]["evidence_sufficient"] is True
    assert response["think_trace"]["generator_called"] is True
    assert response["think_trace"]["cited_chunk_ids"] == ["primary-1"]
    assert response["think_trace"]["selected_evidence_chunk_ids"] == ["primary-1"]
    assert response["think_trace"]["retrieval_queries"] == {
        "DC.operation_party": "DC DC형 적립금 운용 주체 근로자",
    }
    assert "[근거]" in response["answer"]


def test_e2e_accepts_api_top_k_without_reopening_raw_retrieval():
    agent = DirectRequirementE2EAgent(
        _Selector(), ScopedFrontendPreparationShadow(_Retriever()), FakeGenerator(),
    )

    response = agent.answer("DC형 적립금은 누가 운용하나요?", top_k=10)

    assert response["think_trace"]["requested_top_k"] == 10
    assert response["think_trace"]["selected_evidence_chunk_ids"] == ["primary-1"]


def test_e2e_passes_the_same_scoped_catalog_contract_to_preparation():
    preparation = _CapturingPreparation()
    agent = DirectRequirementE2EAgent(_Selector(), preparation, FakeGenerator())

    agent.answer("DC형 적립금은 누가 운용하나요?")

    assert preparation.frontend_payload == {
        "status": "selected",
        "active_subject": "DC",
        "selected_requirements": ["DC.operation_party"],
        "allowed_requirements": ["DC.operation_party"],
    }


def test_e2e_stops_before_retrieval_and_generation_for_non_unique_scope():
    agent = DirectRequirementE2EAgent(
        _UnresolvedSelector(), ScopedFrontendPreparationShadow(_Retriever()), FakeGenerator(),
    )
    response = agent.answer("DB와 DC 중 어느 제도인가요?")

    assert response["think_trace"]["assessment_reason"] == "single_subject_frontend_unresolved"
    assert response["think_trace"]["generator_called"] is False
    assert response["retrieved_context"] == []
