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

## 지표 해석

- `hcx_json_parse_success_rate`의 분모는 정책상 HCX 호출을 시도한 38개 질문이다. HCX가 구조화된 `GenerationResult`를 반환한 비율은 24/38(63.2%)이다.
- `citation_validation_rate`의 분모는 JSON·스키마 파싱에 성공한 24개 응답이다. 이 중 21개(87.5%)는 인용 ID가 실제 전달된 검색 근거의 부분집합임을 서버에서 검증했다.
- `hcx_accepted_answer_rate` 21/38(55.3%)는 의미 정확도가 아니라, HCX 응답이 구조화 파싱과 인용 검증을 모두 통과해 시스템이 수용한 비율이다.
- `success` 14건은 gold direct evidence 검색까지 성공한 E2E 단계 결과다. HCX 응답이 수용됐더라도 gold 근거를 Top-10에서 찾지 못한 7건은 `retrieval_failure`로 분류되므로, 수용 답변 21건과 값이 다르다.
- 전체 지연시간은 40개 요청 전체 기준이며, 생성 지연시간은 HCX 응답이 수용된 21개 요청 기준이다.

## 현재 한계와 다음 진단

`max_tokens`를 HCX v3 규격인 `maxTokens`로 수정한 뒤 이 평가를 다시 실행했다. 남은 14건의 JSON·transport 계열 실패와 3건의 citation rejection은 답변 정확도와 별개로 structured generation 안정화가 필요한 사례다. 다음 실험에서는 response truncation, markdown fence 변형, JSON 앞뒤 자연어, 필수 필드 누락, 인용 ID 불일치, HTTP·retry 실패를 분리 집계한다.
