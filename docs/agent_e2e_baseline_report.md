# FakeGenerator E2E 기준선

- 고정 검색 구성: 원본 Corpus 23,421청크, Simple BM25, `pension-v1`
- 40개 질문을 `GET /answer` 계약으로 호출했다.

## 결과

| Metric | Value |
|---|---:|
| api_success_rate | 1.000 |
| generator_invocation_rate | 0.950 |
| evidence_rejection_rate | 0.050 |
| unsupported_handling | 2 |
| citation_validity | 1.000 |
| answerable_retrieval_success | 27 |
| mean_latency_ms | 74.548 |
| p95_latency_ms | 94.634 |

## 단계별 결과

| Stage | Count |
|---|---:|
| evidence_rejection | 2 |
| retrieval_failure | 11 |
| success | 27 |
