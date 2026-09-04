# P26: P24-B Candidate HCX E2E 실행

P24-B retrieval/matcher를 P26 candidate evaluation path에만 포함했다. 기본 브라우저 Agent는 변경하지 않았다. 이 문서는 실행·안정성 결과이며, 새 답변의 semantic quality는 별도 수동 라벨링 전에는 확정하지 않는다.

## 고정 조건

- 모델: `HCX-007`
- P24-B requirement retrieval/matcher candidate
- provenance·금융 답변 정책
- P25-A minimal citation representation 및 strict validator
- HCX request-start 최소 간격: 6초 (guard 0.1초)

## Preparation

- P24-B reference parity: 40/40
- known false rejection: 0
- known unsafe pass: 0

## Provider 실행 결과

- 질문: 40개
- HCX 호출 대상: 37개
- 정책상 사전 차단: 3개
- provider attempt: 39개
- HTTP 200 / 429 / 5xx: 39 / 0 / 0
- provider retry exhaustion: 0
- 최소 request-start 간격(ms): 6100.685

## 다음 단계

`evaluation/p26_candidate_execution.jsonl`의 answer hash별로 semantic correctness, requirement coverage, grounding, answer relevance, hallucination, information-limit handling을 새로 라벨링한다. 이 단계가 끝나기 전에는 Strict E2E Useful 또는 production 승격을 선언하지 않는다.
