# HyperCLOVA X 실패 진단

## Scope

- 이 문서는 정책·프롬프트·파서를 변경하지 않고 동일한 40문항을 진단 목적으로 재실행한 결과다.
- 응답 원문·프롬프트·인증정보는 저장하지 않고 구조 메타데이터와 익명화된 JSON 형태만 기록했다.

## Baseline and diagnostic run

- 기존 baseline: structured-output 실패 14건, citation rejection 3건.
- unpaced diagnostic run: HTTP 429 22건이 관측됐다.
- paced diagnostic run: structured-output 실패 0건, citation rejection 3건.
- `reproduced`는 unpaced run에서의 재현 여부이고, `paced_reproduced`는 요청 간격을 둔 run에서의 재현 여부다.

## Structured-output failure

| Category | Count | Reproduced baseline target |
|---|---:|---:|
| http_retry | 9 | 9 |
| not_reproduced | 5 | 0 |

## Citation validation rejection

| Cause | Count | Reproduced baseline target |
|---|---:|---:|
| missing_citation | 1 | 1 |
| unknown_chunk_id | 2 | 0 |

## Case list

| Question | Group | Category | HTTP | Attempts | Stop reason | Exception | Unpaced reproduced | Paced reproduced |
|---|---|---|---:|---:|---|---|---:|---:|
| R-009 | citation_validation | unknown_chunk_id | 200 | 1 | stop | CitationValidationError | False | True |
| R-012 | citation_validation | unknown_chunk_id | 200 | 2 | stop | CitationValidationError | False | True |
| R-016 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-017 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-018 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-019 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-020 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-021 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-022 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-023 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-025 | structured_output | http_or_transport_failure | 429 | 3 |  | HTTPError | True | False |
| R-026 | structured_output | accepted_or_different_outcome | 200 | 1 | stop |  | False | False |
| R-027 | structured_output | accepted_or_different_outcome | 200 | 1 | stop |  | False | False |
| R-028 | structured_output | accepted_or_different_outcome | 200 | 1 | stop |  | False | False |
| R-029 | structured_output | accepted_or_different_outcome | 200 | 1 | stop |  | False | False |
| R-030 | structured_output | accepted_or_different_outcome | 200 | 1 | stop |  | False | False |
| R-035 | citation_validation | missing_citation | 200 | 1 | stop | CitationValidationError | True | True |

## Root-cause summary

- baseline structured-output 14건 중 9건은 unpaced run에서 HTTP 429와 retry exhaustion으로 직접 재현됐고, paced run에서는 structured-output 실패가 0건이었다. 요청 속도와 provider rate limit은 강한 원인 후보다.
- 나머지 baseline structured-output 5건은 진단 run에서 재현되지 않았으므로 parser·truncation 원인으로 단정하지 않는다.
- citation rejection 3건은 paced run에서 모두 재현됐다(unknown chunk ID 2건, missing citation 1건).

## Fix proposals (not implemented)

- P0: provider rate-limit을 실행환경 수준에서 제어하는 방안을 별도 실험으로 검증한다. Agent의 Fail-Closed 정책은 유지한다.
- P1: unknown chunk ID와 missing citation은 validator를 완화하지 않고 prompt contract 또는 출력 schema 개선 실험으로 분리한다.
- P2: 재현되지 않은 5건은 추가 run에서 response metadata를 축적한 뒤에만 parser·truncation 변경 후보로 승격한다.
