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


def test_product_field_slot_rejects_a_table_of_contents_even_when_it_lists_field_names():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "투자전략",
                ("KR510902511M", "투자전략"),
                2,
                reject_table_of_contents=True,
            ),
        ),
    )
    contents = result(1, "toc", "[목 차] 투자대상 투자전략 투자위험")
    contents.product_codes = ["KR510902511M"]

    selection = RequirementEvidenceSelector().select(case, [contents])

    assert not selection.complete
    assert selection.missing_slot_names == ["투자전략"]


def test_product_field_slot_requires_field_content_not_only_a_generic_field_mention():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "투자대상",
                ("KR510902511M", "투자대상"),
                2,
                required_any_text_terms=("투자비율", "주된 투자대상"),
                forbidden_text_terms=("투자대상이 되는 자산가치",),
            ),
        ),
    )
    generic = result(1, "generic", "투자대상이 되는 자산가치의 가격변동에 따라 손익이 결정됩니다.")
    generic.product_codes = ["KR510902511M"]
    specific = result(2, "specific", "투자대상 투자비율 국내 주식에 60% 이상 투자합니다.")
    specific.product_codes = ["KR510902511M"]

    selection = RequirementEvidenceSelector().select(case, [generic, specific])

    assert selection.complete
    assert selection.contexts[0].chunk_id == "specific"


def test_product_target_canonical_term_still_requires_matching_product_and_value_cue():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "투자대상",
                ("KR510902511M", "투자대상"),
                2,
                canonical_terms=("투자합니다",),
                required_any_text_terms=("이상 투자",),
                reject_table_of_contents=True,
            ),
        ),
    )
    matching = result(1, "matching", "장기성장주 위주로 국내 주식에 최소 60% 이상 투자합니다.")
    matching.product_codes = ["KR510902511M"]
    wrong_product = result(2, "wrong-product", "장기성장주 위주로 국내 주식에 최소 60% 이상 투자합니다.")
    wrong_product.product_codes = ["KR0000000000"]
    missing_value = result(3, "missing-value", "이 투자신탁은 투자합니다.")
    missing_value.product_codes = ["KR510902511M"]

    selection = RequirementEvidenceSelector().select(case, [wrong_product, missing_value, matching])

    assert selection.complete
    assert selection.contexts[0].chunk_id == "matching"


def test_field_value_pattern_accepts_whitespace_split_risk_grade():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "위험등급",
                ("KR5110601022", "위험등급"),
                2,
                required_text_pattern=r"[1-6]\s*등급",
            ),
        ),
    )
    chunk = result(1, "grade", "KR5110601022 위험등급 2 등급")
    chunk.product_codes = ["KR5110601022"]

    assert RequirementEvidenceSelector().select(case, [chunk]).complete


def test_total_fee_slot_does_not_treat_a_cost_example_as_a_total_fee_value():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "총보수",
                ("KR5110501016", "총보수", "총 보수"),
                2,
                required_any_text_terms=("총보수", "총 보수"),
            ),
        ),
    )
    example_only = result(
        1,
        "example-only",
        "KR5110501016 1,000만원 투자 시 총비용 예시: 1년 40천원",
    )
    total_fee = result(2, "total-fee", "KR5110501016 총 보수 0.30%, 기타비용 0.01%")

    selection = RequirementEvidenceSelector().select(case, [example_only, total_fee])

    assert selection.complete
    assert selection.contexts[0].chunk_id == "total-fee"


def test_product_investment_risk_does_not_accept_an_investment_strategy_as_risk_evidence():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "주요 투자 위험",
                ("KR5113420012", "투자위험", "원금손실"),
                2,
                required_any_text_terms=("투자위험", "원금손실"),
            ),
        ),
    )
    strategy = result(1, "strategy", "KR5113420012 투자전략: 국내 주식에 투자합니다.")
    risk = result(2, "risk", "KR5113420012 투자위험: 원금손실 위험이 있습니다.")

    selection = RequirementEvidenceSelector().select(case, [strategy, risk])

    assert selection.complete
    assert selection.contexts[0].chunk_id == "risk"


def test_product_strategy_slot_accepts_conversion_specific_strategy_but_not_unrelated_risk_text():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "전환 후 투자전략",
                ("KR510902511M", "운용전략"),
                2,
                canonical_terms=("운용전환", "채권 중심"),
                required_any_text_terms=("운용전환", "채권 중심"),
            ),
        ),
    )
    unrelated = result(1, "risk", "KR510902511M은 원금손실 가능성이 있습니다.")
    conversion = result(2, "converted", "KR510902511M은 운용전환 후 채권 중심으로 운용합니다.")

    selection = RequirementEvidenceSelector().select(case, [unrelated, conversion])

    assert selection.complete
    assert [context.chunk_id for context in selection.contexts] == ["converted"]


def test_subject_bound_product_slot_rejects_the_same_field_from_another_product():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "KR111 risk grade",
                ("KR111", "위험등급"),
                2,
                required_subject_terms=("KR111",),
                required_text_pattern=r"[1-6]\s*등급",
            ),
        ),
    )
    wrong_product = result(1, "wrong", "위험등급 2등급")
    wrong_product.product_codes = ["KR222"]
    correct_product = result(2, "correct", "위험등급 4등급")
    correct_product.product_codes = ["KR111"]

    selection = RequirementEvidenceSelector().select(case, [wrong_product, correct_product])

    assert selection.complete
    assert [context.chunk_id for context in selection.contexts] == ["correct"]


def test_safety_grade_slot_rejects_a_generic_asset_table_without_grade_explanation():
    case = RequirementCase(
        "safety", "test", (
            RequirementSlot(
                "6등급 의미",
                ("6등급", "위험"),
                3,
                required_all_text_terms=("6등급", "채권", "실제 수익률 변동성"),
                canonical_terms=("채권", "매우 낮은 위험"),
            ),
        ),
    )
    generic_table = result(1, "generic", "주식형 혼합형 채권형 자산유형별 수탁고")
    generic_table.title = "투자 위험 등급 6등급 [매우 낮은 위험]"
    direct_grade = result(
        2,
        "grade",
        "채권 펀드의 실제 수익률 변동성을 감안해 6등급 매우 낮은 위험으로 분류했습니다.",
    )

    selection = RequirementEvidenceSelector().select(case, [generic_table, direct_grade])

    assert selection.complete
    assert [context.chunk_id for context in selection.contexts] == ["grade"]


def test_product_risk_grade_prefers_direct_current_classification_over_history_table():
    case = RequirementCase(
        "product", "test", (
            RequirementSlot(
                "현재 위험등급", ("KR111", "위험등급"), 2,
                key="KR111:risk_grade",
                required_subject_terms=("KR111",),
                required_text_pattern=r"[1-6]\s*등급",
            ),
        ),
    )
    history = result(1, "history", "KR111 위험등급 변경내역: 5등급, 변경일 2023년", score=20.0)
    history.product_codes = ["KR111"]
    current = result(2, "current", "KR111은 투자위험등급 5등급으로 분류하였습니다.", score=1.0)
    current.product_codes = ["KR111"]

    selection = RequirementEvidenceSelector().select(case, [history, current])

    assert selection.complete
    assert selection.contexts[0].chunk_id == "current"


def test_scope_group_binds_related_safety_slots_to_one_source_document():
    case = RequirementCase(
        "target", "test", (
            RequirementSlot(
                "전환 전략", ("목표전환", "채권", "운용"), 2,
                required_any_text_terms=("국내 채권",),
                scope_group="target_product",
            ),
            RequirementSlot(
                "전환 손실", ("보장", "손실"), 2,
                scope_group="target_product",
            ),
        ),
    )
    strategy = result(1, "strategy", "목표전환 후 국내 채권에 주로 투자하여 운용합니다.")
    strategy.source_id = "target-source"
    matching_loss = result(3, "matching-loss", "목표전환 과정에서 손실이 발생할 수 있어 원금을 보장하지 않습니다.")
    matching_loss.source_id = "target-source"
    other_loss = result(2, "other-loss", "이 펀드는 원금을 보장하지 않으며 손실이 발생할 수 있습니다.")
    other_loss.source_id = "other-source"

    selection = RequirementEvidenceSelector().select(case, [strategy, other_loss, matching_loss])

    assert selection.complete
    assert [context.chunk_id for context in selection.contexts] == ["strategy", "matching-loss"]


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
