# P25-B2: HCX 요청 간격 후보 탐색

## 목적

P25-B1에서 확인한 기존 limiter의 start-spacing 보장 부재를 제거한 뒤, Router/Gate·retrieval·prompt·citation·금융 정책을 바꾸지 않고 provider 안정성만 검증했다.

새 limiter는 `time.monotonic()`과 lock을 사용하며, sleep 뒤 남은 시간을 다시 계산한다. 모든 retry도 같은 limiter를 통과한다. 설정값은 request-start의 판정 기준이고, 0.1초 guard는 limiter 예약과 실제 HTTP dispatch 사이의 미세한 jitter를 흡수한다.

## 후보 screen 결과

| 설정 최소 간격 | 실행 문항 | Provider attempt | HTTP 429 | Provider retry exhaustion | 관측 최소 request-start 간격 | 판정 |
|---:|---:|---:|---:|---:|---:|---|
| 3초 | 12 | 15 | 3 | 1 | 3,054.425ms | 탈락 |
| 4초 | 12 | 15 | 3 | 1 | 4,057.765ms | 탈락 |
| 5초 | 10 | 13 | 1 | 0 | 5,052.177ms | 탈락 |

각 screen은 첫 429가 포함된 문항 처리를 마친 뒤 종료했다. 5초 후보의 429는 재시도로 복구됐지만, 후보 선별 규칙인 `HTTP 429 = 0`을 만족하지 못했다. 별도로 관측된 JSON/schema 실패는 provider retry exhaustion과 분리했다.

## 해석

세 후보 모두 실제 request-start가 설정 최소 간격 이상이었다. 따라서 P25-B의 1,944.91ms 간격 위반은 해결됐지만, provider 429는 사라지지 않았다. 특히 3초와 4초는 R-012에서, 5초는 R-010에서 발생했으며 Retry-After는 한 번도 제공되지 않았다.

이 결과만으로 provider quota의 정확한 window 또는 token 기준을 확정할 수는 없다. 다만 단순한 단일 요청 간격 위반만으로 설명하기 어렵고, sliding-window·token quota·같은 API key의 외부 사용 여부를 운영 변수로 계속 취급해야 한다.

## 결론

P25-B2는 **No-Go**다. 3초·4초·5초 후보 모두 full 38~40문항 안정성 실행으로 승격하지 않는다. `retry exhaustion = 0`뿐 아니라 screen에서 `HTTP 429 = 0`을 만족하는 실행 조건을 찾기 전에는 P26 Full Controlled E2E를 실행하지 않는다.
