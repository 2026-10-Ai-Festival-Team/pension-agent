# P25-B4: 6초 Full Sequential Provider 안정성

## 실행 조건

- HCX-007, 현재 기본 Agent 구성 고정
- 38개 answerable 요청을 단일 프로세스에서 순차 실행
- 설정 최소 간격 6초, limiter 예약 간격 6.1초
- Router/Gate, retrieval, prompt, citation validator, 금융 정책은 변경하지 않음

## 결과

| 지표 | 결과 |
|---|---:|
| HCX 호출 대상 | 38 |
| Provider attempt | 40 |
| HTTP 200 | 40 |
| HTTP 429 | 0 |
| 5xx | 0 |
| Timeout | 0 |
| Provider retry attempt | 0 |
| Provider retry exhaustion | 0 |
| 최소 request-start 간격 | 6,028.069ms |
| 평균 request-start 간격 | 6,128.629ms |
| 전체 실행 시간 | 240,851.137ms |

Provider attempt가 40인 것은 두 응답의 JSON/schema 재시도에 따른 것이며, provider 429/5xx 재시도는 없었다. 이 보고서는 해당 JSON/schema 품질을 semantic 성공으로 해석하지 않는다.

## 판정

**P25-B Go.** 6초 pacing은 이번 38-call sequential run에서 `HTTP 429 = 0`, `provider retry exhaustion = 0`을 만족했다. 따라서 provider/runtime blocker는 이 실행 조건에서 해소됐으며, P26 Controlled E2E를 진행할 수 있다.

이 결과는 단일 key·단일 프로세스·해당 provider 상태에서의 검증이다. 별도 환경에서 같은 credential을 동시에 사용하면 안정성 보장은 다시 검증해야 한다.
