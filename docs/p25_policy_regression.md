# P25-0: Provenance·금융 답변 정책 회귀 검증

HCX를 호출하지 않고 기본 `PensionAgent`의 기존 evidence gate와 provenance gate를 비교했다. 이 결과는 P24-B 실험 경로의 검색·matcher 성능을 측정하지 않는다.

## 결과

| 범위 | 문항 | provenance 신규 false rejection | augmented-only unsafe pass | 예상 차단 누락 |
|---|---:|---:|---:|---:|
| Full-40 | 40 | 0 | 0 | 0 |
| P15 mini-holdout | 12 | 0 | 0 | 0 |

## 답변 정책 확인

- 세제 유의사항 누락: 0건
- 일반 제도 질문의 불필요한 유의사항: 0건
- 추천 역질문 누락: 0건
- 원본·1차 근거가 아닌 citation: 0건

## 기존 Corpus provenance migration

- 청크 수: 23421개
- `original + primary`: 23421개
- `augmented`: 0개
- 정책상 모순된 provenance 조합: 0개

## 해석

`provenance 신규 false rejection`은 provenance 조건을 추가하기 전에는 통과했지만, 원본·1차 근거가 없어서 새로 차단된 경우만 뜻한다. 검색 recall이나 compound requirement completeness로 인한 기존 차단은 이 P25-0 지표에 포함하지 않는다.

P25-0 통과 기준은 provenance 신규 false rejection 0, augmented-only unsafe pass 0, 예상 차단 누락 0이다.
