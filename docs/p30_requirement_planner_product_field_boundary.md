# P30: Requirement Planner & Product Field Boundary

## Scope

- HCX 호출 없음; corpus, BM25 파라미터, prompt, citation validator는 변경하지 않음
- 기존 shared preparation 경로에서 requirement plan과 slot matcher만 검증
- 총보수·기타비용·투자 비용 예시를 서로 대체하지 않는 canonical field로 분리

## Planner target cases

| ID | Expected slots | Generated slots | Gate | Contexts |
|---|---|---|---|---:|
| R-011 | retirement_income_transfer_tax_deferral, retirement_income_annuity_tax_timing | retirement_income_transfer_tax_deferral, retirement_income_annuity_tax_timing | pass | 2 |
| R-019 | dc_withdrawal_eligibility, dc_withdrawal_legal_grounds | dc_withdrawal_eligibility, dc_withdrawal_legal_grounds | reject | 1 |
| R-035 | KR5113420012:investment_risk, KR5113420012:principal_loss_possible | KR5113420012:investment_risk, KR5113420012:principal_loss_possible | pass | 2 |
| R-038 | early_withdrawal_eligibility, early_withdrawal_legal_grounds | early_withdrawal_eligibility, early_withdrawal_legal_grounds | pass | 2 |

## Product field boundary

- R-034 generated fields: KR5110501016:total_fee, KR5110501016:investment_target
- `total_fee`, `other_expenses`, `example_cost`는 각각 별도 slot이며, 비용 예시만으로 총보수 slot을 충족하지 않는다.

## Offline regression

- Shared preparation parity: 40/40
- P15 mini-holdout route/gate regressions: 0
- Known false rejection: 0
- Known unsafe pass: 0
- Mean selected context count: 6.88

## Decision

Go only for offline candidate validation when all target plans, shared-path parity, and P15 route/gate checks pass. Semantic answer quality requires a separate, controlled HCX evaluation.
