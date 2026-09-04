from src.experiments.scope_reference_resolver import DeterministicBinder, ScopeReferenceResolver


def test_ordinal_product_reference_resolves_only_the_second_explicit_product():
    resolution = ScopeReferenceResolver().resolve("KR5114420022와 KR5114450222 중 뒤에 적은 상품의 위험등급은?")
    result = DeterministicBinder().bind("KR5114420022와 KR5114450222 중 뒤에 적은 상품의 위험등급은?", resolution, ("product.risk_grade.current",))

    assert resolution.active_subjects == ("product:KR5114450222",)
    assert result.bindings[0].subject == "product:KR5114450222"


def test_ordinal_account_reference_resolves_second_explicit_account():
    resolution = ScopeReferenceResolver().resolve("DB와 DC 중 두 번째 제도의 운용 주체는 누구인가요?")

    assert resolution.active_subjects == ("DC",)
    assert resolution.references[0].kind == "ordinal_subject_reference"


def test_ambiguous_anaphora_stays_unresolved_instead_of_widening_scope():
    resolution = ScopeReferenceResolver().resolve("DB와 DC를 비교할 때 그 제도의 운용 주체는 누구인가요?")
    result = DeterministicBinder().bind("DB와 DC를 비교할 때 그 제도의 운용 주체는 누구인가요?", resolution, ("DB.operation_party",))

    assert resolution.unresolved_references == ("그 제도",)
    assert "그 제도" in result.unresolved_references
    assert result.bindings[0].status == "unresolved_reference"


def test_ambiguous_singular_product_reference_stays_unresolved_without_ordinal_cue():
    question = "KR5114420022와 KR5114450222를 비교할 때 그 상품의 위험등급은 무엇인가요?"
    resolution = ScopeReferenceResolver().resolve(question)
    result = DeterministicBinder().bind(question, resolution, ("product.risk_grade.current",))

    assert resolution.unresolved_references == ("그 상품",)
    assert result.bindings[0].status == "unresolved_reference"
    assert result.bindings[0].subject is None


def test_ambiguous_singular_type_reference_stays_unresolved_across_systems():
    question = "DB와 DC를 함께 언급한 뒤 그 유형의 운용 주체를 물으면 누구를 뜻하나요?"
    resolution = ScopeReferenceResolver().resolve(question)
    result = DeterministicBinder().bind(question, resolution, ("DB.operation_party", "DC.operation_party"))

    assert resolution.unresolved_references == ("그 유형",)
    assert {item.status for item in result.bindings} == {"unresolved_reference"}


def test_closed_pair_contrast_resolves_dc_but_binder_does_not_add_missing_operation_requirement():
    question = "퇴직급여가 미리 정해지는 DB와 달리 근로자 성과에 따라 달라지는 쪽은 무엇이며 적립금 선택은 누가 하나요?"
    resolution = ScopeReferenceResolver().resolve(question)
    result = DeterministicBinder().bind(question, resolution, ("DB.benefit_determination", "DC.benefit_determination"))

    assert resolution.active_subjects == ("DC",)
    assert any("DB:DB.benefit_determination" in item for item in result.scope_conflicts)
    assert result.incomplete_reasons == ("selector_multi_requirement_incomplete:operation_party",)
    assert {item.requirement for item in result.bindings} == {"DB.benefit_determination", "DC.benefit_determination"}


def test_selector_scope_anchor_can_resolve_single_anaphora_but_not_add_the_missing_requirement():
    question = "회사 부담금이 매년 임금에 따라 정해져 적립되는 제도는 어느 것이고, 그 계좌 운용방법은 누가 고르나요?"
    resolution = ScopeReferenceResolver().resolve(question)
    result = DeterministicBinder().bind(question, resolution, ("DC.employer_contribution",))

    assert resolution.unresolved_references == ("그 계좌",)
    assert result.active_subjects == ("DC",)
    assert result.incomplete_reasons == ("selector_multi_requirement_incomplete:operation_party",)


def test_dc_expanded_korean_entity_alias_resolves_without_the_acronym():
    resolution = ScopeReferenceResolver().resolve("확정기여형퇴직연금에서 회사 부담금은 어떻게 정해지나요?")

    assert resolution.explicit_subjects == ("DC",)
    assert resolution.active_subjects == ("DC",)


def test_future_temporal_wording_is_not_misread_as_an_ordinal_first_reference():
    resolution = ScopeReferenceResolver().resolve(
        "KR5127420045의 현재 위험등급은 몇 등급이며, 문서상 이 등급은 앞으로도 고정인가요?"
    )

    assert resolution.active_subjects == ("product:KR5127420045",)
    assert resolution.unresolved_references == ()


def test_exclusive_scope_resolves_only_the_included_account():
    resolution = ScopeReferenceResolver().resolve("IRP를 함께 쓰지 않고 연금저축만 납입하면 한도는 얼마인가요?")

    assert resolution.active_subjects == ("pension_savings",)
    assert resolution.references[0].kind == "exclusive_scope"


def test_exclusive_scope_supports_excluding_and_standalone_forms():
    excluding = ScopeReferenceResolver().resolve("IRP를 제외하고 연금저축의 공제 한도를 알려주세요.")
    standalone = ScopeReferenceResolver().resolve("연금저축 단독으로 적용되는 공제 한도는 얼마인가요?")

    assert excluding.active_subjects == ("pension_savings",)
    assert standalone.active_subjects == ("pension_savings",)


def test_exclusive_scope_connector_family_retains_include_and_exclude_roles():
    cases = (
        ("IRP 없이 연금저축만 납입한 공제 한도", "pension_savings", "IRP"),
        ("IRP 제외하고 연금저축 공제 한도를 알려주세요", "pension_savings", "IRP"),
        ("IRP는 빼고 연금저축 계좌에만 납입한 경우", "pension_savings", "IRP"),
        ("IRP를 빼고 연금저축 한도만 확인", "pension_savings", "IRP"),
        ("IRP 말고 연금저축 한도를 알려주세요", "pension_savings", "IRP"),
        ("IRP가 아닌 연금저축만 공제 한도를 확인", "pension_savings", "IRP"),
        ("IRP가 아니라 연금저축만 공제 한도를 확인", "pension_savings", "IRP"),
    )

    for question, included, excluded in cases:
        resolution = ScopeReferenceResolver().resolve(question)
        assert resolution.active_subjects == (included,)
        assert resolution.references[0].kind == "exclusive_scope"
        assert resolution.references[0].excluded_subjects == (excluded,)


def test_additive_or_comparison_wording_is_not_forced_to_exclusive_scope():
    additive = ScopeReferenceResolver().resolve("IRP 말고 연금저축도 가능한가요?")
    comparison = ScopeReferenceResolver().resolve("IRP와 연금저축을 비교해 주세요.")
    simple_negative = ScopeReferenceResolver().resolve("IRP가 아닌 계좌의 한도는 무엇인가요?")

    assert additive.active_subjects == ("IRP", "pension_savings")
    assert comparison.active_subjects == ("IRP", "pension_savings")
    assert simple_negative.active_subjects == ("IRP",)


def test_plain_negative_or_genuine_pair_is_not_misread_as_exclusive_scope():
    negative = ScopeReferenceResolver().resolve("IRP가 아닌 연금저축과 IRP의 차이는 무엇인가요?")
    pair = ScopeReferenceResolver().resolve("DB와 DC의 운용 주체를 각각 알려주세요.")

    assert negative.active_subjects == ("IRP", "pension_savings")
    assert pair.active_subjects == ("DB", "DC")


def test_confirmation_or_self_doubt_suffix_does_not_change_a_single_db_scope():
    resolution = ScopeReferenceResolver().resolve("DB는 내가 직접 굴리는 거 맞지? 아닌가?")

    assert resolution.active_subjects == ("DB",)
    assert not resolution.references
    assert not resolution.unresolved_references
