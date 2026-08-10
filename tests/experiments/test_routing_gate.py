from src.experiments.multi_evidence import RequirementCase, RequirementSlot
from src.experiments.routing_gate import ExperimentalRouteGate, ExperimentalRouter
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.query_analyzer import QueryAnalyzer


def result(text, title="product title"):
    return SearchResult(rank=1, chunk_id="c", score=1, text=text, source_id="s", source_path="x", source_format="pdf", document_type="d", locator=ChunkLocator(page_start=1, page_end=1), title=title)


def test_router_identifies_compound_korean_bound_entities_and_product_topics():
    router = ExperimentalRouter()
    analyzer = QueryAnalyzer()

    assert router.classify(analyzer.analyze("DB형과 DC형의 퇴직급여 산정 방식은?")).route == "compound"
    assert router.classify(analyzer.analyze("KR510902511M 상품의 투자대상과 운용전략은?")).route == "compound"
    assert router.classify(analyzer.analyze("상품코드 KR510902511M의 상품명과 위험등급을 알려주세요.")).route == "compound"
    assert router.classify(analyzer.analyze("KR5117420097의 기준일과 운용전략을 찾아주세요.")).route == "compound"
    assert router.classify(analyzer.analyze("판매수수료와 총보수ㆍ비용은 어디에 표시되나요?")).route == "simple"
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


def test_simple_gate_uses_a_requirement_template_when_one_is_defined():
    analysis = QueryAnalyzer().analyze("DC형 중도인출 조건")
    case = RequirementCase(
        "R",
        "test",
        (RequirementSlot("DC 법정사유", ("DC", "법정사유"), 2),),
    )

    decision = ExperimentalRouteGate().assess("simple", analysis, [result("DC 법정사유 충족시 가능")], case)

    assert decision.sufficient
    assert decision.reason == "simple_requirements_complete"


def test_requirement_slot_can_require_terms_to_be_locally_coherent():
    case = RequirementCase(
        "R",
        "test",
        (RequirementSlot("같은 근거 구간", ("DC", "무주택"), 2, max_term_span=10),),
    )

    decision = ExperimentalRouteGate().assess("simple", QueryAnalyzer().analyze("DC 조건"), [result("DC " + "x" * 20 + " 무주택")], case)

    assert not decision.sufficient


def test_compound_product_fields_get_generic_code_bound_requirement_slots():
    analysis = QueryAnalyzer().analyze("KR510902511M 상품명과 위험등급을 알려주세요")

    decision = ExperimentalRouteGate().assess(
        "compound",
        analysis,
        [result("KR510902511M 상품명 위험등급")],
    )

    assert decision.sufficient
    assert decision.reason == "compound_requirements_complete"


def test_product_name_slot_requires_a_titled_product_context():
    analysis = QueryAnalyzer().analyze("KR510902511M 상품명과 위험등급을 알려주세요")
    untitled = SearchResult(
        rank=1,
        chunk_id="c",
        score=1,
        text="KR510902511M 위험등급",
        source_id="s",
        source_path="x",
        source_format="pdf",
        document_type="d",
        locator=ChunkLocator(page_start=1, page_end=1),
    )

    decision = ExperimentalRouteGate().assess("compound", analysis, [untitled])

    assert not decision.sufficient
    assert decision.missing_slots == ["KR510902511M product_name"]
