# P32-B: Generalized Orchestration Offline Regression

## Scope

- HCX 호출 없음
- P32는 P32-A attribution 이후 개발 회귀셋으로만 사용
- Corpus, BM25 파라미터, citation validator, provider pacing은 변경하지 않음

## Results

- P15 route/gate regressions: **0**
- P31 previously-sufficient preparation regressions: **0**
- P32 expected deterministic behavior: **25/25**

## P32 failed-case owners after generalized preparation

| ID | Route | Requirement category | Gate/policy result |
|---|---|---|---|
| P32-002 | compound | irp_contribution_and_tax_deduction_limit | compound_requirements_complete |
| P32-006 | compound | db_dc_benefit_calculation | compound_requirements_complete |
| P32-009 | compound | db_dc_conversion | compound_requirements_complete |
| P32-010 | compound | irp_withdrawal_and_cancellation | compound_requirements_complete |
| P32-012 | compound | product_fields | compound_requirements_complete |
| P32-013 | compound | product_fields | compound_requirements_complete |
| P32-014 | simple | product_fields | simple_requirements_complete |
| P32-015 | compound | product_fields | compound_requirements_complete |
| P32-016 | policy | - | conditional_recommendation_requires_user_conditions |
| P32-017 | policy | - | recommendation_comparison_only |
| P32-018 | policy | - | conditional_recommendation_requires_user_conditions |
| P32-019 | policy | - | personal_tax_conditions_required |
| P32-020 | unsupported | personal_account_lookup | personal_account_lookup |
| P32-021 | unsupported | - | unsupported_or_personal_or_conditional |
| P32-022 | unsupported | personal_account_lookup | personal_account_lookup |
| P32-025 | simple | past_performance_premise | simple_requirements_complete |

## Interpretation

This report verifies deterministic preparation behavior only. It does not relabel answers, call HCX, or establish P32 as a generalized quality score. Any P32 improvement must be validated on a new frozen P33 holdout.
