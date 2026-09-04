# P30-Live: Limited HCX Semantic Reevaluation

## Fixed conditions

- P30 requirement planner and product-field boundary
- HCX-007 Native Structured Outputs, thinking none, 6-second pacing
- strict parser, strict citation validator, Financial Policy
- no prompt, retrieval, workflow, or validator tuning

## Execution contract

- HCX attempted: 8/8 eligible cases
- JSON/schema success: 8/8
- Citation validation: 8/8
- Provider 429 / 5xx: 0 / 0
- R-019: HCX not called; DC-specific detailed statutory grounds were not sufficiently isolated from IRP-only evidence.

## Semantic labels

| ID | Role | Correctness | Coverage | Grounding | Strict useful |
|---|---|---|---|---|---:|
| R-011 | target | correct | full | fully_supported | yes |
| R-035 | target | correct | full | fully_supported | yes |
| R-038 | target | partial | partial | partially_supported | no |
| R-034 | target | correct | full | fully_supported | yes |
| R-019 | fail_closed_control | not_evaluable | missing | unsupported | no |
| R-001 | control | correct | full | fully_supported | yes |
| R-002 | control | correct | full | fully_supported | yes |
| R-004 | control | correct | full | fully_supported | yes |
| R-008 | control | correct | full | fully_supported | yes |

## P30 target delta

- P27-E target baseline: 0/4 strict useful (`R-011`, `R-034`, `R-035`, `R-038`).
- P30-Live target result: 3/4 strict useful.
- Improved: R-011 (IRP 이전 과세 시점), R-034 (총보수와 투자대상), R-035 (주요 투자 위험).
- Remaining: R-038은 법정사유는 제시했지만 계정 유형별 적용 범위를 구분하지 않아 partial로 유지한다.

## Decision

**P30-Live Go.** P30 requirement slots improved the limited target set without control regression, provider failure, schema failure, or citation regression. This is a small semantic result only; Full-40 candidate execution is a separate decision.
