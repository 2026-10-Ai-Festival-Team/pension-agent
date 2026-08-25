from types import SimpleNamespace

from src.experiments.read_only_shadow_integration import ReadOnlyScopedShadowObserver
from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResponse, SearchResult


class _Retriever:
    def search(self, query, top_k):
        return SearchResponse(
            query=query,
            tokenizer="simple",
            total_candidates=1,
            results=[SearchResult(
                rank=1, chunk_id="evidence-1", score=1.0, text="IRP 인출 과세 원본 근거",
                source_id="source-1", source_path="guide.pdf", source_format="pdf", document_type="guide",
                locator=ChunkLocator(page_start=1, page_end=1), source_type=SourceType.ORIGINAL,
                authority_level=AuthorityLevel.PRIMARY,
            )],
        )


class _ScopedSelector:
    def select(self, _question):
        return SimpleNamespace(
            status="selected", active_subject="IRP",
            allowed_requirements=("IRP.withdrawal.tax_treatment",),
            selection=SimpleNamespace(selected_requirements=("IRP.withdrawal.tax_treatment",)),
            reason=None,
        )


def test_observer_records_preparation_without_any_answer_dependency():
    observer = ReadOnlyScopedShadowObserver(
        _ScopedSelector(), ScopedFrontendPreparationShadow(_Retriever()),
    )

    record = observer.observe("IRP 인출 세금")

    assert record.status == "prepared"
    assert record.active_subject == "IRP"
    assert record.context_ids == ("evidence-1",)
    assert len(record.question_sha256) == 64
    assert observer.records == [record]


def test_observer_contains_selector_exception():
    class _ExplodingSelector:
        def select(self, _question):
            raise RuntimeError("shadow only")

    record = ReadOnlyScopedShadowObserver(
        _ExplodingSelector(), ScopedFrontendPreparationShadow(_Retriever()),
    ).observe("IRP 인출 세금")

    assert record.status == "shadow_exception"
    assert record.exception_type == "RuntimeError"
