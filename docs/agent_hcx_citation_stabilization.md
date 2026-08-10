# HCX 인용 계약 안정화 (P1)

## 목표

P0에서 확정한 단일 프로세스 전역 2초 minimum interval을 유지한 채, paced HCX run의 인용 거부 3건을 개별 분석했다. 목표는 수용률을 인위적으로 높이는 것이 아니라 정상 인용의 false rejection만 제거하고, 잘못되거나 누락된 인용은 계속 fail-closed로 차단하는 것이다.

고정 조건은 원본 Corpus 23,421청크, Simple BM25, `pension-v1`, HCX-DASH-002, `maxTokens=800`, global minimum interval 2초, bounded retry다.

## 기준선

| 지표 | 값 |
|---|---:|
| HCX attempted | 38 |
| Structured JSON parse | 38/38 |
| Accepted answer | 35/38 (92.1%) |
| `unknown_chunk_id` | 2 |
| validator의 `missing_citation` | 1 |

`Accepted answer`는 정확성 지표가 아니라 구조·인용 계약을 모두 통과한 HCX 호출 비율이다.

## 사례 분석

모델 답변 본문은 저장하지 않았다. 실제 응답의 인용 구조만 보존한 secret-free fixture는 `tests/fixtures/hcx_citation_cases/`에 있다. 아래의 normalized question은 현재 `QueryAnalyzer`가 공백 trim만 적용한 결과로 질문 원문과 같다.

| ID | Normalized question | Ordered allowed `chunk_id` | HCX parsed `cited_chunk_ids` | Primary cause | Exact mismatch |
|---|---|---|---|---|---|
| R-009 | 퇴직급여를 연금으로 받으면 과세는 어떻게 되나요? | `93b9…-d442`, `ef05…-7894`, `7878a3be5806fef4-paragraph_group-d24f4b2854ed`, … | `7878a3be5806fef4` | `wrong_identifier_type` | 허용된 완전한 chunk ID가 아닌 source ID만 반환 |
| R-012 | 세액공제 대상이 되는 연금계좌 납입금의 조건은 무엇인가요? | `…`, `4ae16261de11da35-table-bdf681407cec`, `…`, `4ae16261de11da35-table-cae3223cb315`, `1bfc399c9b3d6a67-table-c9ca47302c31`, … | `4ae16261de11da35`, `1bfc399c9b3d6a67` | `wrong_identifier_type` | source ID만 반환. 특히 `4ae…`는 허용된 서로 다른 두 chunk에 해당해 결정적으로 복원할 수 없음 |
| R-035 | KR5113420012에 해당하는 펀드의 주요 투자 위험은 무엇인가요? | `c61c1c27df94646e-paragraph_group-e93fa0ad0c80`, `c61c…-907d`, … | `[]` | `empty_citation` | `cited_chunk_ids` field는 존재하지만 빈 배열 |

R-009와 R-012의 HTTP status는 200, structured JSON parse는 성공, `finish_reason`은 `stop`이었다. R-035도 HTTP 200과 parse 성공이며 markdown fence만 제거됐다. 따라서 세 사례는 transport·truncation·parser 손실이 아니다.

현재 validator의 외부 사유 문자열 `missing_citation`은 빈 배열과 field 누락을 함께 나타낸다. 이 보고서의 primary-cause taxonomy에서는 R-035를 정확히 `empty_citation`으로 기록한다.

## 원인과 변경

실제 3건은 HCX가 인용 계약을 지키지 않은 경우였다. 허용 목록이 full `chunk_id`만 제공했음에도 R-009·R-012는 source ID를 반환했고, R-035는 빈 배열을 반환했다.

이에 prompt contract만 최소 강화했다.

- answer가 있으면 `cited_chunk_ids`에 full allowed `chunk_id`를 하나 이상 그대로 복사해야 함
- 빈 배열 금지
- `source_id`, 문서명, 경로, 페이지, ID 일부는 인용 ID가 아님
- 새 ID 생성·ID 축약·변형 금지

서버 citation validator, retrieval, corpus, chunk ID, retry 정책은 변경하지 않았다.

## 안전 제약

다음 동작은 의도적으로 도입하지 않았다.

- source ID·문서·페이지에서 chunk ID를 역추론하는 매핑
- prefix·suffix·edit distance 기반 fuzzy match
- top-1 검색 결과로 누락 인용을 채우는 보정
- answer 본문에 문서명이 있다는 이유만으로 citation 생성
- whitespace trim을 포함한 citation canonicalization

특히 R-012의 `4ae16261de11da35`는 두 개의 허용 chunk ID의 같은 source 접두부이므로 어떤 자동 복원도 근거 위치를 임의로 선택하게 된다. 이는 fail-closed 원칙과 충돌한다.

## Native structured output 검토

공식 Chat Completions v3 structured-output 문서는 JSON Schema 기능을 **HCX-007에서만** 제공한다고 명시한다. 현재 배포 모델은 HCX-DASH-002이므로 이 기능을 P1에 도입하지 않았다. 또한 dynamic allowed chunk ID enum을 model request마다 강제하는 것은 현 모델 계약에서 검증되지 않았다. [CLOVA Studio Structured Outputs 문서](https://api.ncloud-docs.com/docs/en/clovastudio-chatcompletionsv3-so)

## 회귀 테스트

fixture 기반으로 다음을 확인한다.

| Case | Expected |
|---|---|
| 유효한 단일·복수 allowed citation | pass |
| R-009·R-012 source ID 반환 | `unknown_chunk_id`로 fail-closed |
| `cited_chunk_ids` field 누락 | `missing_citation`으로 fail-closed |
| R-035 빈 배열 | `missing_citation`으로 fail-closed |
| 공백을 포함한 ID | `unknown_chunk_id`로 fail-closed |

## E2E 재평가

동일 40문항을 P0와 같은 2초 global interval 조건으로 한 번 재실행하고, 이전 paced run과 별도로 Git 제외 진단 파일에 기록한다. 실행 결과는 아래 표에 추가한다.

| Run | Parse | Accepted | Accepted rate | `unknown_chunk_id` | empty / missing citation |
|---|---:|---:|---:|---:|---:|
| Before (paced) | 38/38 | 35/38 | 92.1% | 2 | 1 |
| After (P1) | 33/38 | 31/38 | 81.6% | 0 | 2 |

P1 run에는 인용 계약과 무관한 provider·format failure 5건이 섞였다. HTTP 429 retry exhaustion 4건(R-014, R-030, R-032, R-034)과 HTTP 200 응답의 malformed JSON 1건(R-012)이다. 그러므로 `31/38`을 baseline `35/38`과 인용 프롬프트의 효과로 직접 비교하지 않는다. 2초는 P0에서의 최소 **테스트** 안정점이며, provider 상태가 달라진 이 실행에서 429 0을 보장하지 못했다.

같은 run에서 structured parse에 성공한 33건 중 citation validator 통과는 31건(93.9%)이며, 인용 거부는 R-024와 R-035의 빈 배열 2건이었다. `unknown_chunk_id`는 관측되지 않았다. R-009는 accepted 되었지만, R-012는 세 번 모두 malformed JSON이어서 새 prompt의 citation 행동을 관측할 수 없었다. 한 번의 확률적 HCX run만으로 source-ID 오류가 prompt 변경 때문에 제거됐다고 인과적으로 단정하지 않는다.

Git 제외 진단 결과는 `data/diagnostics/agent_hcx_citation_stabilization_run.json`에 보존한다.

## 남은 한계

- 프롬프트 강화는 모델의 인용 준수를 유도할 뿐, provider-side enum 제약은 아니다.
- 수용률은 semantic accuracy나 retrieval quality를 나타내지 않는다.
- P1 재평가에서 2초 global interval에도 429가 재발했다. 실제 provider quota는 시간대·계정 상태에 따라 변할 수 있으므로, P0 정책은 fixed guarantee가 아니라 현재 단일 프로세스의 최소 테스트 안정점이다.
- 멀티-worker 배포에는 P0 limiter와 별도로 distributed rate limiter가 필요하다.
