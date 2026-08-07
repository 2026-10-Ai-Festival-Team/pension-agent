# HyperCLOVA X E2E 기준선

- 고정 검색 구성: 원본 Corpus 23,421청크, Simple BM25, `pension-v1`
- 40개 질문을 실제 HCX 생성기와 `GET /answer` 계약으로 평가했다.
- 입력·출력 토큰 사용량은 HCX 응답의 `usage` 제공 여부에 따라 진단 JSON에만 기록한다.

## 결과

| Metric | Value |
|---|---:|
| question_count | 40 |
| api_success_rate | 1.0 |
| hcx_attempt_rate | 0.95 |
| hcx_json_parse_success_rate | 0.632 |
| citation_validation_rate | 0.875 |
| hcx_accepted_answer_rate | 0.553 |
| hcx_json_or_transport_failure_count | 14 |
| citation_rejection_count | 3 |
| mean_total_latency_ms | 2019.536 |
| p95_total_latency_ms | 5316.776 |
| mean_generation_latency_ms | 2618.824 |
| p95_generation_latency_ms | 6586.223 |
| usage_available_count | 21 |

## 단계별 결과

| Stage | Count |
|---|---:|
| evidence_rejection | 2 |
| generation_failure | 13 |
| retrieval_failure | 11 |
| success | 14 |
