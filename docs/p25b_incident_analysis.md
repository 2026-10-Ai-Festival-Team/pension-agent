# P25-B1: Provider Rate-limit Incident Analysis

## 범위

P25-B의 기존 40문항 순차 실행 telemetry만 분석했다. HCX 재호출, prompt, retrieval, Router/Gate, citation validator, 금융 정책 변경은 수행하지 않았다.

## 확인 결과

- 설정 최소 간격: 2.000초
- 실제 start 간격 최솟값: 1944.91ms
- 설정 간격 미만 start 간격: 20건
- provider attempt: 57건
- HTTP 상태: {'200': 29, '429': 28}
- retry attempt: 19건; limiter wait telemetry 보존: 19건
- Retry-After 관측: 0건
- 첫 429: `R-013` attempt 1 (직전 start 간격 3875.15ms, 직전 30초 요청 10건)

## 원인 판단

기존 limiter는 `time.monotonic()`을 사용했고 retry도 limiter를 거쳤다. 다만 미래 슬롯을 예약한 뒤 sleep을 한 번만 수행했으므로, OS의 조기 wake-up 뒤 실제 request start가 설정값보다 빨라질 수 있었다. P25-B의 1,944.91ms 최소 간격은 이 엄격 보장이 없었다는 직접 증거다.

429가 긴 정상 응답 구간 이후에도 군집해 발생했으므로, 이 간격 오차만으로 28건 전체를 설명할 수는 없다. provider sliding-window/token quota 또는 동일 API key의 외부 사용 가능성이 남아 있다. P25-B 종료 후 로컬 프로세스를 확인했을 때 별도 평가 스크립트의 동시 HCX 호출은 확인되지 않았지만, 외부 프로세스·다른 환경의 같은 키 사용 여부는 이 telemetry만으로 확인할 수 없다.

## 조치

1. limiter를 sleep 후 남은 시간을 다시 계산하는 loop와 actual-start 기준 예약으로 교체했다.
2. pacing guard를 설정화해 실제 request-start 간격이 `minimum interval + guard` 이상이 되도록 했다.
3. P25-B2에서는 3초 후보를 10~15문항 screen으로 먼저 검증하고, 429가 발생하면 즉시 다음 후보(4초, 필요 시 5초)로 넘어간다.
4. full sequential run의 필수 통과 기준은 retry exhaustion 0이다.
