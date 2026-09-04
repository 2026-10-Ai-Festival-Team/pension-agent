# P31: Full-40 Candidate E2E 실행

P30 requirement planner와 product-field boundary를 포함한 single-pass candidate를 고정 조건으로 실행했다. 이 보고서는 운영·안전 계약만 기록한다. semantic 품질은 새 answer hash를 대상으로 별도 수동 라벨링한다.

## 고정 조건

- HCX-007 Native Structured Outputs (`thinking.effort=none`)
- P24-B retrieval/matcher candidate
- P29 provenance/financial answer policy
- P30 requirement planner/product-field boundary
- strict parser, strict citation validator, Fail-Closed
- global HCX request-start interval: 6초 + guard

## P30 Offline Preflight

- shared preparation parity: 40/40
- known false rejection: 0
- known unsafe pass: 0
- P15 route/gate regressions: 0

## 실행 결과

| 항목 | 결과 |
|---|---:|
| API 200 | 40/40 |
| HCX 호출 대상 | 37 |
| HTTP 429 / 5xx / timeout | 0 / 0 / 0 |
| Retry exhaustion | 0 |
| JSON/schema failure | 0 |
| Empty answer / citation | 0 / 0 |
| Citation validator failure | 0 |
| 최소 request-start 간격(ms) | 6100.372 |
| R-019 HCX 호출 | False |
| R-039 / R-040 안전 차단 | True / True |

## P30 Target Preparation

| ID | Route | Gate | Requirement slots | Selected evidence |
|---|---|---|---:|---:|
| R-011 | compound | compound_requirements_complete | 2 | 2 |
| R-034 | compound | compound_requirements_complete | 2 | 2 |
| R-035 | compound | compound_requirements_complete | 2 | 2 |
| R-038 | compound | compound_requirements_complete | 2 | 2 |

## 다음 단계

`evaluation/p31_candidate_execution.jsonl`의 `answer_hash`별로 semantic correctness, requirement coverage, grounding, policy behavior, strict useful을 새로 라벨링한다. 이 실행만으로 Strict E2E Useful 또는 production 승격을 선언하지 않는다.
