# P39-0 — Direct Canonical Requirement Selector Decision

## Decision

`P38-7B`의 semantic-atom parser는 candidate 경로에 통합하지 않는다.

- semantic requirement coverage: 48.8%
- requirement exact: 6/18
- essential qualifier F1: 30.0%
- directional relation accuracy: 50.0%
- real semantic miss: 22
- unsupported extra atom: 16

HCX가 `subject / field / qualifier / relation`을 매번 안정적으로 생성한 뒤
requirement로 다시 조합하도록 요구하는 구조는 Closed factual에 적합하지 않다.

다음 실험 후보는 자연어 질문에서 **허용된 canonical requirement를 직접 여러 개
선택**하는 방식이다. 이것은 아직 설계·개발셋 검증 단계이며, 현재 브라우저
candidate나 retrieval/gate에는 연결하지 않는다.

## Inventory result

현재 `RequirementBuilder`에는 69개의 raw slot key가 있다. 이는 69개의 서로
다른 사실이 아니라 다음과 같은 문맥별 중복을 포함한다.

- `db_operation`, `db_dc_operation_party` → `DB.operation_party`
- `dc_operation`, `db_dc_operation_party` → `DC.operation_party`
- `irp_withdrawal_legal_grounds`, `irp_withdrawal_legal_grounds_comparison`
  → `IRP.early_withdrawal.allowed_reasons`
- `pension_savings_tax_deduction_limit`, `pension_savings_only_deduction_limit`
  → `pension_savings.tax_credit.limit`
- `isa_transfer_additional_tax_credit` → `ISA.transfer.additional_deduction`

상품은 product code를 deterministic entity resolver가 먼저 확정하고, selector는
아래 `product.<field>`만 고르게 한다. 즉 상품명이나 product ID를 HCX가 새로
만들 수 없다.

## Provisional canonical vocabulary

### Institution and structure

```text
DB.operation_party
DC.operation_party
DB.benefit_determination
DC.benefit_determination
DC.employer_contribution
retirement_pension.regulation.content
retirement_pension.regulation.representative_consent
retirement_benefit.severance_payment
retirement_benefit.pension_external_accumulation
IRP.eligibility
IRP.contribution.limit
participant_education.provider
participant_education.frequency
participant_education.outsourcing
```

### Tax and account treatment

```text
pension_savings.tax_credit.limit
pension_savings_IRP.tax_credit.combined_limit
IRP.tax_credit.limit
pension_account.tax_deferral.timing
pension_account.annuity.age
pension_account.annuity.minimum_duration
pension_account.annuity.limit
pension_account.cancellation.additional_tax
pension_account.non_annuity.tax
pension_account.cancellation.exception
retirement_income.transfer.tax_deferral
retirement_income.annuity.tax_timing
ISA.transfer.deadline
ISA.transfer.additional_deduction
ISA.transfer.non_deducted_principal.tax_treatment
foreign_ETF.general_account.tax
foreign_ETF.pension_account.tax_timing
foreign_ETF.tax.condition
```

### Procedures and restrictions

```text
DC.early_withdrawal.allowed_reasons
DC.early_withdrawal.required_documents
IRP.early_withdrawal.allowed_reasons
IRP.account_closure.condition
IRP.account_closure.tax
retirement_pension.in_kind_transfer.meaning
retirement_pension.in_kind_transfer.allowed_routes
retirement_pension.in_kind_transfer.application.DB_DC
retirement_pension.in_kind_transfer.application.IRP
retirement_pension.ETF.direct_trade_scope
retirement_pension.ETF.leverage_inverse_restriction
```

### Product factual fields

```text
product.name
product.manager
product.risk_grade.current
product.risk_grade.change_possibility
product.total_fee
product.other_expense
product.period_cost
product.investment_target
product.investment_strategy
product.asset_type
product.principal_loss_possible
product.principal_guarantee_status
product.effective_date
product.tracking_index
```

### Premise correction and comparison

```text
past_performance.not_future_guarantee
past_performance.not_suitability_proof
product.deposit_protection_status
product.risk_grade_meaning
```

## Proposed P39-1 contract

```json
{
  "selected_requirements": [
    "DC.early_withdrawal.allowed_reasons",
    "DC.early_withdrawal.required_documents"
  ],
  "resolved_product_codes": [],
  "unresolved": false
}
```

Rules:

1. `selected_requirements` is a schema enum; the model cannot invent names.
2. Product codes come only from deterministic resolution.
3. Comparison is derived from the selected requirements and resolved subjects;
   it is not a free-form relation atom.
4. Directional transfers remain explicit only where direction changes the fact
   (for example, `ISA → IRP`).
5. Unknown or low-confidence mappings set `unresolved=true`; they never
   silently broaden retrieval.

## Evaluation sequence

1. Freeze this vocabulary after human review.
2. Map existing Closed Core/P34–P38 development questions to the catalog.
3. Compare three development-only paths:
   - legacy deterministic planner,
   - frozen P38 atom parser,
   - direct canonical requirement multi-label selector.
4. Measure requirement recall, precision, exact multi-label match, unresolved
   precision, and wrong-scope evidence. Do not use a development score as a
   generalisation claim.
5. Only the winning frozen design proceeds to a fresh holdout.

## Non-goals

- No P38 prompt or ontology patch.
- No HCX answer generation, retrieval, matcher, citation, policy, or browser
  candidate change in P39-0.
- No question-ID branches or forced gold evidence.
