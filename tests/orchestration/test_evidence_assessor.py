from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.evidence_assessor import EvidenceAssessor
from src.orchestration.query_analyzer import QueryAnalyzer


def result(text="DB와 DC 비교", codes=None):
    return SearchResult(rank=1, chunk_id="c", source_id="s", source_path="x.pdf", source_format="pdf", document_type="pension_guide", locator=ChunkLocator(page_start=1, page_end=1), element_ids=["e"], score=1, text=text, product_codes=codes or [])


def test_assessor_blocks_missing_product_code_evidence():
    analysis = QueryAnalyzer().analyze("KR5144420081 상품 설명")
    assert EvidenceAssessor().assess(analysis, [result()]).reason == "product_code_evidence_missing"


def test_assessor_requests_conditions_for_recommendation():
    analysis = QueryAnalyzer().analyze("어떤 상품을 추천해 주세요")
    assessment = EvidenceAssessor().assess(analysis, [result()])
    assert not assessment.sufficient
    assert "위험 성향" in assessment.missing_requirements
