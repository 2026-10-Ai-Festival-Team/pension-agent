from types import SimpleNamespace

from src.experiments.multi_evidence import RequirementCase, RequirementSlot
from src.experiments.requirement_retrieval import expand_requirement_candidates
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult


def _result(chunk_id: str) -> SearchResult:
    return SearchResult(
        rank=1,
        chunk_id=chunk_id,
        score=1.0,
        text="개인형퇴직연금제도 가입자의 연금 지급기간은 5 년 이상입니다.",
        source_id="source",
        source_path="guide.pdf",
        source_format="pdf",
        document_type="guide",
        title="개인형 퇴직연금제도(IRP)",
        locator=ChunkLocator(page_start=1, page_end=1),
    )


class _Retriever:
    def __init__(self, result: SearchResult) -> None:
        self.result = result
        self.queries: list[str] = []

    def search(self, query: str, top_k: int):
        self.queries.append(query)
        return SimpleNamespace(results=[self.result])


class _AnchorRetriever(_Retriever):
    def __init__(self, result: SearchResult, anchor: SearchResult) -> None:
        super().__init__(result)
        self.anchor = anchor
        self.anchor_requests: list[tuple[str, str, int]] = []

    def product_field_anchors(self, product_code: str, field: str, top_k: int):
        self.anchor_requests.append((product_code, field, top_k))
        return (self.anchor,)


def test_requirement_candidate_expansion_preserves_base_results_and_adds_only_unique_hits():
    base = _result("base")
    expanded = _result("duration-evidence")
    retriever = _Retriever(expanded)
    case = RequirementCase(
        "case",
        "test",
        (RequirementSlot("기간", ("IRP", "5 년"), 2, retrieval_query="개인형 퇴직연금 5년"),),
    )

    candidates = expand_requirement_candidates(case, [base], retriever, top_k=3)

    assert [item.chunk_id for item in candidates] == ["base", "duration-evidence"]
    assert retriever.queries == ["개인형 퇴직연금 5년"]


def test_requirement_candidate_expansion_is_disabled_at_zero_top_k():
    base = _result("base")
    retriever = _Retriever(_result("unused"))
    case = RequirementCase(
        "case",
        "test",
        (RequirementSlot("기간", ("IRP",), retrieval_query="개인형 퇴직연금"),),
    )

    assert expand_requirement_candidates(case, [base], retriever, top_k=0) == (base,)
    assert retriever.queries == []


def test_product_field_anchor_is_added_without_replacing_bm25_candidates():
    base = _result("base")
    bm25 = _result("bm25")
    anchor = _result("direct-risk-grade")
    retriever = _AnchorRetriever(bm25, anchor)
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "위험등급", ("KR111", "위험등급"), 2,
                key="KR111:risk_grade", retrieval_query="KR111 위험등급",
            ),
        ),
    )

    candidates = expand_requirement_candidates(case, [base], retriever, top_k=3)

    assert [item.chunk_id for item in candidates] == ["base", "bm25", "direct-risk-grade"]
    assert retriever.anchor_requests == [("KR111", "risk_grade", 3)]
