from src.experiments.multi_evidence import RequirementCase, RequirementSlot
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.query_analyzer import QueryAnalyzer


def result(text):
    return SearchResult(rank=1, chunk_id="c", score=1, text=text, source_id="s", source_path="x", source_format="pdf", document_type="d", locator=ChunkLocator(page_start=1, page_end=1))


def test_router_identifies_compound_korean_bound_entities_and_product_topics():
    router = ExperimentalRouter()
    analyzer = QueryAnalyzer()

    assert router.classify(analyzer.analyze("DB형과 DC형의 퇴직급여 산정 방식은?")).route == "compound"
    assert router.classify(analyzer.analyze("KR510902511M 상품의 투자대상과 운용전략은?")).route == "compound"
    assert router.classify(analyzer.analyze("IRP 개인부담금 한도는?")).route == "simple"


def test_compound_gate_requires_every_requirement_slot():
    analysis = QueryAnalyzer().analyze("DB와 DC 비교")
    case = RequirementCase("R", "test", (RequirementSlot("DB", ("DB", "회사"), 2), RequirementSlot("DC", ("DC", "근로자"), 2)))
    gate = ExperimentalRouteGate()

    decision = gate.assess("compound", analysis, [result("DB는 회사가 운용")], case)

    assert not decision.sufficient
    assert decision.missing_slots == ["DC"]


def test_simple_gate_does_not_require_compound_slots():
    analysis = QueryAnalyzer().analyze("IRP 한도")

    decision = ExperimentalRouteGate().assess("simple", analysis, [result("IRP 납입 한도")])

    assert decision.sufficient
