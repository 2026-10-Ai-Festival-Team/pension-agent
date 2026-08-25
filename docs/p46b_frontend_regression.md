# P46-B Front-end Regression

P46은 fresh E2E 실행 뒤 개발 회귀셋으로 전환했다. 이 회귀는 answer generation을 호출하지 않고 resolver → scoped selector → binder → preparation까지만 확인한다.

## Generalized changes

1. **Ordinal/reference boundary**: bare `앞`은 순서 지시어로 해석하지 않는다. `앞으로`처럼 시간 표현은 explicit product code의 single-subject scope를 무효화하지 않는다.
2. **DB benefit-formula interpretation**: 기존 canonical requirement `DB.benefit_determination`의 설명을 퇴직급여 산식/계산 방식과 `퇴직 전 평균임금 30일분 × 계속근로기간`까지 명시한다. 새 중복 enum은 만들지 않는다.
3. **Product fee precision**: `product.total_fee`와 `product.period_cost`는 별도 factual field이며, 질문이 각각을 독립적으로 요구할 때만 둘을 함께 선택하도록 selector contract를 강화한다.

## Regression result

| Run | Targets | Scope correct | Requirement exact | Gold direct evidence | Answer HCX calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| P45-B existing regression | 2 | 2/2 | 2/2 | 2/2 | 0 |
| P46-B front-end regression | 3 | 3/3 | 3/3 | 3/3 | 0 |

P46-B validates P46-003, P46-010, and P46-017. It made three live selector calls with Native Structured Output and the established six-second pacing; it did not call answer generation or change candidate/browser behavior.

## Decision

**Regression Go.** This is not a fresh-generalization result. P47 must be a newly frozen single-subject Closed E2E holdout, with no additional front-end changes between its manifest freeze and execution.
