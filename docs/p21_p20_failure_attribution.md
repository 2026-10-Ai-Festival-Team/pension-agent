# P21: P20 Failure Attribution 및 Rate-limit Incident 분석

## 목적

P20의 `Strict E2E Useful 15/38`을 하나의 architecture 점수로 해석하지 않고,
provider incident와 정상 HCX 응답 후의 semantic quality를 분리했다. 이 단계는
P20 raw artifact와 answer-hash-bound review만 읽으며 HCX를 재호출하거나
router/gate/retrieval/prompt를 변경하지 않는다.

P19→P20 shared preparation parity는 이미 40/40이고 known false rejection 및
unsafe pass도 각각 0으로 재현됐으므로, 이번 분석은 Router/Gate 재설계가 아니라
실행 관측과 HCX 후단 품질에 초점을 둔다.

## 세 분모

| Metric | Definition | Result | 용도 |
|---|---|---:|---|
| Unconditional Strict E2E Useful | strict useful / answerable 38 | **15 / 38 = 39.5%** | 실제 한 번의 실행 성능; 보존 |
| Provider-successfully-evaluable | provider 429 retry exhaustion 13건만 제외 | **15 / 25 = 60.0%** | architecture 진단 전용 |
| Strict no-429 subset | 어느 attempt에도 429가 없던 질문만 | **13 / 23 = 56.5%** | 더 보수적인 provider-clean 진단 |

두 provider-clean 값은 공식 점수나 P16과 직접 비교할 지표가 아니다. provider
failure에 의해 answer 자체를 평가할 수 없었던 질문을 제외해, conditional
architecture가 남긴 진짜 품질 문제의 크기를 보는 diagnostic metric이다.

## 정상 HCX 실행 후 semantic quality

P20에서 `provider response → JSON/schema → citation validation`을 모두 통과한
수용 answer는 18개다. 이 중 strict useful은 15개이고 **정상 HCX 후 semantic
failure는 3개**다.

| ID | Failure | Owner |
|---|---|---|
| R-011 | 과세 시점 질문에 압류보호 근거를 선택 | evidence selection / answer relevance |
| R-033 | 상품명만 답하고 위험등급을 누락 | requirement coverage |
| R-034 | 시간별 비용 예시를 총보수 값으로 오해 | product-field interpretation |

따라서 P20이 보여 주는 후단 개선 backlog는 Router/Gate가 아니라 위 세 유형의
generation/evidence-selection 문제다. 이들은 provider failure 13건과 별도다.

## Provider incident

| Observation | Count |
|---|---:|
| HCX attempted questions | 33 |
| HTTP attempts recorded | 64 |
| HTTP 429 attempts | 42 |
| 429가 있었던 질문 | 15 |
| 429 retry exhaustion | 13 |
| 429 뒤 정상 수용으로 회복 | 2 (R-007, R-020) |
| HTTP 200 뒤 JSON/schema failure | 1 (R-012) |
| Citation validation rejection | 1 (R-035) |

429는 R-001~R-007, R-013~R-018, R-038에 집중됐고 R-007/R-020은 재시도 후
회복됐다. 순차 실행 중 연속 burst처럼 보이지만, P20 historic artifact에는
attempt별 request timestamp와 limiter wait가 보존되지 않았다. 따라서 **2초
limiter가 P20에서 실제로 깨졌다고 증명할 수는 없고**, provider의 시간대·계정
quota·외부 사용량이 달랐다는 가설도 아직 확정할 수 없다.

P0 문서도 2초를 영구 quota 보장이 아닌 단일 프로세스의 최소 테스트 안정점으로
정의했다. P20은 그 한계를 다시 확인한 incident이며, architecture 회귀 증거는 아니다.

## 관측성 보완

다음 실행부터 HCX attempt history에는 raw prompt나 인증정보 없이 아래 메타데이터를
각 attempt마다 저장한다.

```text
attempt count
attempt/request start·completion offset
rate-limit wait
HTTP status
numeric Retry-After
retry delay / outcome
```

P20 과거 artifact에는 이 필드가 없어 `historical_attempt_timing_complete = 0/64`다.
따라서 P20의 정확한 request 간격을 사후 복원하지 않고, 이후 controlled run에서만
실측한다.

## 다음 실행의 조건부 프로토콜

HCX 재실행은 이 분석만으로 수행하지 않는다. 사용자가 명시적으로 승인할 때 다음
조건으로 단 한 번 실행한다.

1. 동일 P20 artifact·Corpus·model·generation config와 한 프로세스만 사용한다.
2. 전역 limiter의 per-attempt timing artifact를 저장한다.
3. provider key의 다른 호출이 없는 cooldown 구간을 확보한다.
4. 짧은 canary로 429/Retry-After를 먼저 관측하고, 429가 발생하면 full-40을 시작하지
   않는다.
5. canary가 안정적일 때만 fixed pacing을 명시해 full-40을 한 번 실행한다.
6. unconditional Strict E2E와 provider-clean diagnostic을 모두 다시 보고한다.

그 controlled run에서도 provider-clean subset에서 R-011/R-033/R-034 유형이
반복되면, 다음 개선 우선순위는 compound context/prompt 및 product-field answer
contract가 된다. 반대로 실패가 대부분 provider incident로 사라지면 conditional
architecture의 production 후보 여부를 다시 평가한다.

## 산출물

- [P21 attribution JSON](../evaluation/p21_failure_attribution.json)
- `scripts/analyze_p20_failures.py`
- `src/evaluation/p20_failure_attribution.py`

원문 answer/context와 provider diagnostics는 계속 Git 제외
`data/diagnostics/`에만 저장한다.
