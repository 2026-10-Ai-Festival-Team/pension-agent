# P26: P24-B 대상 실행 Delta

P26 candidate path의 실제 HCX-007 실행 결과를 P24-B가 직접 다룬 네 사례에 한정해 기록한다. 아래 표는 generation 전 근거 확보·citation 계약·호출 상태만 나타내며, semantic correctness와 requirement coverage는 새 answer hash 기반 수동 라벨링 전에는 `pending`이다.

| ID | P24-B 이전 병목 | P26 gate | 선택 근거 | HCX 호출 | Citation validation | Semantic review |
|---|---|---|---|---|---|---|
| R-010 | 해지 과세 예외 matcher | pass | 해지 과세 표 2개 | 성공 | pass | pending |
| R-024 | 상품 위험등급 retrieval | pass | 동일 상품 투자대상·위험등급 표 | 성공 | pass | pending |
| R-028 | 투자대상 canonical matcher | pass | 동일 상품 투자전략 표 | 성공 | pass | pending |
| R-037 | DB/DC 운용 주체 retrieval | pass | DB/DC 비교표 | 성공 | pass | pending |

## 실행상 분리 사항

- P26 preparation parity: 40/40
- HTTP 429 / provider retry exhaustion: 0 / 0
- HCX 호출 대상: 37개, 정상적으로 generation result를 반환한 요청: 35개
- R-004와 R-035는 HTTP 200 이후 JSON/schema 검증에서 `GenerationResponseError`가 발생했다. 이는 provider rate limit이나 P24-B retrieval/matcher의 실패로 분류하지 않는다.

다음 semantic review에서는 위 네 사례가 질문의 모든 요구를 답했는지, 인용 근거가 각 claim을 실제로 지지하는지를 별도로 판정한다.
