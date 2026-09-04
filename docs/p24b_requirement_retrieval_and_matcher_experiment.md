# P24-B: Requirement별 Retrieval 및 Canonical Matcher 실험

## 목적

P24-A에서 확인된 네 건의 원인을 분리해, Corpus·BM25 파라미터·HCX·Fail-Closed 정책을 바꾸지 않고 다음만 실험했다.

1. R-024와 R-037: requirement별 보조 검색어로 필요한 근거를 후보 집합에 추가한다.
2. R-010과 R-028: 동일 subject와 실제 value가 확인된 경우에만 slot별 canonical 표현을 인정한다.

운영 `PensionAgent`는 변경하지 않았고 HCX 호출도 수행하지 않았다.

## 변경 범위

| 유형 | 제한적 변경 | 안전 조건 |
|---|---|---|
| 위험등급 retrieval | `상품코드 + 위험등급 + 실제 수익률 변동성` requirement query | 상품코드 필터, `[1-6]등급` 패턴, 목차 제외 유지 |
| DB/DC 운용 주체 retrieval | DB와 DC 각각에 대한 운용 주체 subquery | 기존 원 질문 Top-k 보존 후 중복 제거 |
| 해지 과세 예외 matcher | `부득이한·연금외수령·연금소득세`의 같은 근거 구간 확인 | 세율/연금소득세 value cue 중 하나 필수 |
| 투자대상 matcher | 상품코드 + 투자대상 canonical value 표현(`투자합니다` 등) | 해당 상품코드, 투자 value cue, 목차 제외를 모두 요구 |

이는 범용 fuzzy matching이나 `source_id → chunk_id` 자동 보정이 아니다. canonical 표현은 requirement slot에 한정되며, product field는 상품코드와 실제 field value를 함께 만족해야 한다.

## 대상 결과

| ID | 이전 gate | 이후 gate | 선택 근거 | 판정 |
|---|---|---|---|---|
| R-010 | reject: 해지 과세 예외 누락 | pass | 기존 세금 표 유지 | `부득이한 연금외수령 사유`를 예외 근거로 정확히 인식 |
| R-024 | reject: 위험등급 누락 | pass | 상품의 위험등급 표 + 기존 투자대상 표 | requirement query가 4등급/보통위험 근거를 회수 |
| R-028 | reject: 투자대상 누락 | pass | 기존 동일 상품의 투자전략 표 유지 | 국내 주식 최소 60% 투자라는 value를 투자대상으로 인식 |
| R-037 | reject: DB/DC 운용 주체 누락 | pass | `doc11.pdf` DB/DC 비교표 | 두 subquery 모두 해당 표를 후보로 회수 |

R-024는 기존 1쪽 gold chunk 자체가 아니라 같은 상품 설명서 5쪽의 동등한 위험등급 표를 회수했다. 질문의 4등급/보통위험 요구를 직접 지지하므로 exact gold ID miss와 semantic evidence miss를 구분했다.

## Full-40 영향

| 측정 | 이전 | 이후 |
|---|---:|---:|
| Shared preparation parity | 40/40 | 40/40 |
| 후보 청크 수 합계 | 425 | 437 |
| HCX에 전달될 선택 context 수 합계 | 305 | 308 |
| 상태가 바뀐 질문 | - | R-010, R-024, R-028, R-033, R-037 |

선택 context 증가는 R-024의 위험등급 근거, R-037의 비교표, 그리고 R-033의 실제 위험등급 표 검증으로 총 3개다. P15 mini-holdout 12문항에서는 route 또는 gate pass/reject 회귀가 없었다.

## 라벨 해석 주의

기존 P11 Full-40 라벨은 P24-B 이전 후보 집합을 기준으로 R-010·R-028·R-037을 `partial` 또는 `none`으로 기록했다. 새 후보·선택 근거를 그 옛 라벨에 기계적으로 대입하면 세 건을 false `unsafe pass`로 계산하게 된다.

P24-A 원문·Corpus 감사와 현재 선택 근거 검토를 근거로, 이 보고서에서는 네 대상 모두 **현재 후보 집합에서 충분한 근거가 있는지**를 별도로 판정했다. 기존 라벨 파일은 덮어쓰지 않았고, P24-B 실험 결과의 정답률 또는 최종 E2E 수치로도 사용하지 않는다.

## 산출물과 검증

- [실험 결과 JSON](../evaluation/p24b_offline_experiment.json)
- [P15 mini-holdout 결과](../evaluation/p24b_p15_mini_holdout_results.jsonl)
- `scripts/summarize_p24b_offline_experiment.py`

검증:

```text
Shared preparation parity: 40/40
P15 route/gate regression: 0
Target gate pass: 4/4
Focused tests: 27 passed
```

## 결정

`candidate_for_follow_up_review`

P24-B는 네 대상의 retrieval/matcher 병목을 오프라인에서 해소했지만, 아직 production 통합이나 HCX 재실행을 승인하지 않는다. 다음 단계 전에 현재 context 기준 semantic sufficiency 라벨을 별도 review artifact로 고정하고, 이후 P24-B citation 계약(R-002/R-006) 및 provider 안정성 분석과 분리해 판단한다.
