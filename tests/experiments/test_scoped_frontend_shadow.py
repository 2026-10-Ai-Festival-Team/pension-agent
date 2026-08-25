from src.experiments.scoped_frontend_shadow import ScopedFrontendPreparationShadow
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
from src.models.retrieval import SearchResponse, SearchResult


class _Retriever:
    def __init__(self):
        self.queries = []

    def search(self, query, top_k):
        self.queries.append(query)
        return SearchResponse(
            query=query,
            tokenizer="simple",
            total_candidates=1,
            results=[
                SearchResult(
                    rank=1, chunk_id="primary-1", score=1.0, text="원본 근거", source_id="source-1",
                    source_path="guide.pdf", source_format="pdf", document_type="guide",
                    locator=ChunkLocator(page_start=1, page_end=1), source_type=SourceType.ORIGINAL,
                    authority_level=AuthorityLevel.PRIMARY,
                )
            ],
        )


class _ProductAnchorRetriever(_Retriever):
    def __init__(self):
        super().__init__()
        self.anchor_requests = []

    def product_field_anchors(self, product_code, field, top_k):
        self.anchor_requests.append((product_code, field, top_k))
        response = self.search("anchor", top_k)
        return tuple(response.results)


class _DirectFieldRetriever(_Retriever):
    def search(self, query, top_k):
        self.queries.append(query)
        return SearchResponse(
            query=query,
            tokenizer="simple",
            total_candidates=2,
            results=[
                SearchResult(
                    rank=1, chunk_id="period-cost", score=2.0, text="투자기간 1,000만원 투자시 비용 예시",
                    source_id="source-1", source_path="fund.pdf", source_format="pdf", document_type="investment_product",
                    product_codes=["KR5114450222"], locator=ChunkLocator(page_start=1, page_end=1),
                    source_type=SourceType.ORIGINAL, authority_level=AuthorityLevel.PRIMARY,
                ),
                SearchResult(
                    rank=2, chunk_id="annual-total-fee", score=1.0, text="지급비율(연간, %) 총 보수 0.95",
                    source_id="source-1", source_path="fund.pdf", source_format="pdf", document_type="investment_product",
                    product_codes=["KR5114450222"], locator=ChunkLocator(page_start=2, page_end=2),
                    source_type=SourceType.ORIGINAL, authority_level=AuthorityLevel.PRIMARY,
                ),
            ],
        )


class _TaxTimingRetriever(_Retriever):
    def search(self, query, top_k):
        self.queries.append(query)
        return SearchResponse(
            query=query,
            tokenizer="simple",
            total_candidates=2,
            results=[
                SearchResult(
                    rank=1, chunk_id="transfer-route", score=2.0, text="퇴직급여를 IRP로 이전할 수 있습니다",
                    source_id="source-1", source_path="guide.pdf", source_format="pdf", document_type="guide",
                    locator=ChunkLocator(page_start=1, page_end=1), source_type=SourceType.ORIGINAL,
                    authority_level=AuthorityLevel.PRIMARY,
                ),
                SearchResult(
                    rank=2, chunk_id="tax-timing", score=1.0, text="이연퇴직소득은 연금수령시 과세됩니다",
                    source_id="source-1", source_path="guide.pdf", source_format="pdf", document_type="guide",
                    locator=ChunkLocator(page_start=2, page_end=2), source_type=SourceType.ORIGINAL,
                    authority_level=AuthorityLevel.PRIMARY,
                ),
            ],
        )


def test_shadow_prepares_requirement_scoped_context_without_calling_a_candidate_agent():
    retriever = _Retriever()
    plan = ScopedFrontendPreparationShadow(retriever).prepare(
        "IRP 인출 과세", {
            "status": "selected", "active_subject": "IRP",
            "allowed_requirements": ["IRP.withdrawal.tax_treatment"],
            "selected_requirements": ["IRP.withdrawal.tax_treatment"],
        },
    )

    assert plan.status == "prepared"
    assert plan.requirement_candidates == {"IRP.withdrawal.tax_treatment": ("primary-1",)}
    assert [item.chunk_id for item in plan.contexts] == ["primary-1"]


def test_product_retrieval_query_uses_only_resolved_product_not_competing_raw_question_codes():
    retriever = _ProductAnchorRetriever()
    ScopedFrontendPreparationShadow(retriever).prepare(
        "KR5114420022와 KR5114450222 중 후자의 연간 총보수율", {
            "status": "selected", "active_subject": "product:KR5114450222",
            "allowed_requirements": ["product.total_fee"],
            "selected_requirements": ["product.total_fee"],
        },
    )

    assert retriever.queries == ["KR5114450222 총보수 지급비율 연간"]
    assert "KR5114420022" not in retriever.queries[0]


def test_product_risk_field_uses_direct_anchor_after_scope_is_resolved():
    retriever = _ProductAnchorRetriever()
    plan = ScopedFrontendPreparationShadow(retriever).prepare(
        "A상품과 B상품 중 후자의 현재 위험등급", {
            "status": "selected", "active_subject": "product:KR5114450222",
            "allowed_requirements": ["product.risk_grade.current"],
            "selected_requirements": ["product.risk_grade.current"],
        },
    )

    assert plan.status == "prepared"
    assert retriever.anchor_requests == [("KR5114450222", "risk_grade", 2)]
    assert "A상품" not in retriever.queries[0]


def test_total_fee_direct_field_signal_excludes_period_cost_example():
    plan = ScopedFrontendPreparationShadow(_DirectFieldRetriever()).prepare(
        "상품의 연간 총보수", {
            "status": "selected", "active_subject": "product:KR5114450222",
            "allowed_requirements": ["product.total_fee"],
            "selected_requirements": ["product.total_fee"],
        },
    )

    assert plan.requirement_candidates == {"product.total_fee": ("annual-total-fee",)}


def test_tax_timing_direct_field_signal_excludes_transfer_route_only_evidence():
    plan = ScopedFrontendPreparationShadow(_TaxTimingRetriever()).prepare(
        "퇴직급여를 IRP로 이체한 뒤 과세 시점", {
            "status": "selected", "active_subject": "IRP",
            "allowed_requirements": ["retirement_income.IRP_transfer.tax_timing"],
            "selected_requirements": ["retirement_income.IRP_transfer.tax_timing"],
        },
    )

    assert plan.requirement_candidates == {"retirement_income.IRP_transfer.tax_timing": ("tax-timing",)}


def test_shadow_preserves_unresolved_as_no_retrieval():
    plan = ScopedFrontendPreparationShadow(_Retriever()).prepare(
        "그 계좌", {"status": "unresolved_scope", "reason": "unresolved_reference"},
    )

    assert plan.status == "unresolved_scope"
    assert plan.contexts == ()
