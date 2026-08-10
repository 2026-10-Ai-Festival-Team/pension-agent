# HyperCLOVA X Provider Rate-Limit 제어 실험

## Objective

HCX structured-output parser·prompt·citation validator를 변경하지 않고, 호출 밀도가 HTTP 429와 HCX Accepted Answer Rate에 미치는 영향을 측정했다. 모든 run은 동일한 40문항, 23,421청크 Corpus, Simple BM25, `pension-v1`, HCX-DASH-002, `maxTokens=800`, 기존 bounded retry를 사용했다.

## 기존 기준선과 진단 run

| Run | 성격 | HCX attempted | HTTP 429 | Parse | Accepted | 비고 |
|---|---|---:|---:|---:|---:|---|
| 초기 E2E baseline | no pacing | 38 | 미기록 | 24 | 21 | 당시 attempt-level HTTP 관측 없음 |
| unpaced diagnostic | no pacing | 38 | 22 | 16 | 15 | provider rate-limit 오염 확인 |
| 6초 paced diagnostic | fixed pacing | 38 | 0 | 38 | 35 | 기존 안정 상한 기준점 |

초기 baseline의 구조화 실패 14건을 모두 429로 단정하지 않는다. unpaced diagnostic에서 9개 baseline 대상이 429·retry exhaustion으로 직접 재현됐고, 5개는 재현되지 않았다.

## Fixed pacing 실험

분모는 HCX attempted 38건이다. `JSON parse`는 structured `GenerationResult`가 생성된 건수, `Citation pass`와 `Accepted`는 citation validator를 통과한 건수다.

| Pacing | 429 HTTP attempts | Retry exhaustion | Parse | Citation pass | Accepted | Accepted rate | Mean / p95 total | Run time | Throughput |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1초 | 12 | 4 | 34 | 31 | 31 | 81.6% | 2.38s / 5.82s | 137.2s | 16.62 rpm |
| 2초 | 0 | 0 | 38 | 35 | 35 | 92.1% | 2.58s / 6.09s | 185.0s | 12.32 rpm |
| 3초 | 0 | 0 | 37 | 35 | 35 | 92.1% | 2.48s / 6.12s | 221.3s | 10.30 rpm |
| 6초 | 0 | 0 | 38 | 35 | 35 | 92.1% | 2.50s / 6.07s | 별도 진단 run | N/A |

## 결과와 trade-off

- 1초는 처리량은 높지만 429 12회와 retry exhaustion 4건이 발생해 평가용 설정으로 채택할 수 없다.
- 2초와 3초는 모두 429 0건·Accepted 35/38을 기록했다.
- 따라서 **2초는 최소 테스트 안정점**이며, 3초·6초보다 약 20%·40% 높은 처리량을 제공한다. 이는 단일 run 기준의 실험적 최소값이지 provider quota의 영구적 보장은 아니다.
- 35/38은 contract acceptance이며, 답변 정확도나 retrieval 성능 지표가 아니다.

## Recommended policy

단일 API 서버의 현재 사용 조건에서는 복잡한 bucket보다 다음이 최소 변경 정책이다.

```text
전역 minimum interval: 2초
동시성: generator 인스턴스 전체에서 공유
retry: 최대 2회 유지
429/5xx: bounded retry, Retry-After 숫자 헤더가 있으면 우선 사용
401/403 및 기타 non-retryable 4xx: 즉시 실패
```

`GlobalMinIntervalLimiter`는 thread-safe slot reservation을 사용하므로 동시 FastAPI 요청이 들어와도 worker별 sleep이 아니라 generator 전체의 요청 시작 간격을 제어한다. 실제 외부 concurrency=2/4 run은 provider quota 비용을 피하기 위해 실행하지 않았으며, concurrent caller에 대한 전역 간격은 fake clock 기반 단위 테스트로 검증했다.

## Risks

- limiter는 단일 Python 프로세스 기준이다. Uvicorn worker를 여러 개 띄우거나 서버를 수평 확장하면 Redis 등 공유 limiter가 필요하다.
- HTTP `Retry-After`가 숫자 초가 아닌 날짜 형식이면 현재는 기록만 하고 fixed bounded delay를 사용한다.
- 남은 citation rejection 3건은 rate limit 문제가 아니며, 다음 단계에서 별도 contract 진단 대상으로 유지한다.

## Production/evaluation configuration

```env
HCX_MIN_INTERVAL_SECONDS=2
HCX_MAX_RETRIES=2
HCX_TIMEOUT_SECONDS=30
```

machine-readable run 기록은 Git 제외 경로 `data/diagnostics/hcx_rate_limit_runs.jsonl`에 저장한다.
