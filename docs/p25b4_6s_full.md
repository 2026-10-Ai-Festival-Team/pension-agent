# P25-B: 순차 HCX Provider 안정성

P25-A 결과를 근거로 citation 계약을 변경하지 않고, 현재 기본 Agent의 기존 prompt·citation·Router/Gate·정책 구성을 그대로 사용해 단일 프로세스에서 순차 실행했다. 이 보고서는 semantic quality나 citation 품질을 평가하지 않는다.

## 실행 조건

- 모델: `HCX-007`
- 요청 수: 38
- HCX 호출 시도: 38
- 정책상 사전 차단: 0
- 전역 최소 간격 설정: 6.0초
- pacing guard: 0.1초
- limiter 예약 간격: 6.1초
- request-start 판정 기준: 설정 최소 간격 이상 (guard는 dispatch jitter 흡수용)

## Provider 원격 측정

- provider attempt: 40
- HTTP 200: 40
- HTTP 429: 0
- 5xx: 0
- timeout: 0
- retry attempt: 0
- retry exhaustion: 0
- Retry-After 관측: 0
- 요청 시작 간격 최소/평균(ms): 6028.069 / 6128.629

## 판정

P25-B의 provider 안정성 통과 기준은 `retry exhaustion = 0`이다. 429와 5xx·timeout은 semantic 품질과 분리해 기록한다. 세부 attempt timestamp와 retry telemetry는 Git 제외 diagnostics에만 저장한다.
