# P34-B Generalized Orchestration / Source-Relevance Fix

## Objective

P34-A에서 드러난 새 표현 일반화 실패를 question ID별 예외가 아니라 canonical requirement와 evidence-binding 규칙으로 보완한다. HCX는 호출하지 않는다.

## Generalized changes

- 비교·외부 위탁·중간 인출 표현을 기존 비교/가입자 교육/중도인출 intent로 정규화했다.
- DB·DC 비교의 동일 사실 축을 `schema_equivalent`로 canonicalize했다. P34-012처럼 동등한 benefit-calculation plan은 planner miss로 세지 않는다.
- 미래 위험등급 변경은 단순 과거 변경 이력이 아니라 `위험등급 + 변경 + 변경될 수/시장 상황`이 chunk 본문에 있는 근거를 요구한다.
- 상품의 지수추종 전략과 주식 관련 자산 비율은 각각 직접 지수 수익률 연동, 주식관련 자산·투자비율 근거를 요구한다. 일반 운용 인력 설명이나 모투자신탁 90% 비율은 대체 근거가 아니다.
- DC 중도인출은 DC scope, 법정 사유, 신청·증빙을 함께 묶어 IRP/무관 세액정산 근거를 대체하지 않도록 했다.
- 일반계좌/연금계좌 과세 시점은 title이 아니라 chunk 본문에 계좌 범위가 있는지 확인한다.

## HCX-free regression

| Check | Result |
| --- | ---: |
| P34 requirement-plan coverage | 18/18 |
| P34 evidence sufficiency | 18/18 |
| P34 selected original + primary | 18/18 |
| P34 source relevance | 10 exact + 8 semantic equivalent = 18/18 |
| P34 partial / wrong scope | 0 / 0 |
| Closed Core evidence sufficiency | 46/46 |
| Product subject-field binding | 8/8 |
| P15/P31 regressions via P32-B suite | 0 / 0 |
| P32 deterministic expected behavior | 25/25 |
| P33 deterministic / first-turn policy | 25/25 / 7/7 |
| P33 source relevance after current revalidation | 18/18 exact or equivalent |
| HCX calls | 0 |
| pytest | 262 passed |

## Evidence adjudication rule

Non-exact chunks are accepted only when the current selected evidence directly supports the same `subject + field + value/condition + account/product/system scope`. The adjudication is bound to the selected chunk IDs in `evaluation/p34b_current_evidence_revalidation.json`; a changed evidence set requires a new review.

## Decision

P34 is now a development regression set, not fresh evidence of generalization. Do not invoke HCX on P34. Freeze a non-overlapping P35 Closed factual holdout and execute the unchanged candidate path next.
