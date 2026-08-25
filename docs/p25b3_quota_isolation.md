# P25-B3: HCX Quota Isolation

## 범위

P25-B2의 3·4·5초 pacing screen telemetry를 재분석했다. Agent, retrieval, prompt, citation, Router/Gate, 금융 정책은 변경하지 않았으며 HCX를 새로 호출하지 않았다.

## 429 위치

| 설정 간격 | 429 위치 | HTTP 429 | retry exhaustion |
|---:|---|---:|---:|
| 3.0초 | #13 R-012 (직전 3075.78ms, 30초 5건/60초 12건), #14 R-012 (직전 3100.225ms, 30초 5건/60초 13건), #15 R-012 (직전 3110.085ms, 30초 5건/60초 14건) | 3 | 1 |
| 4.0초 | #13 R-012 (직전 4060.424ms, 30초 6건/60초 12건), #14 R-012 (직전 4106.233ms, 30초 6건/60초 13건), #15 R-012 (직전 4102.098ms, 30초 6건/60초 14건) | 3 | 1 |
| 5.0초 | #12 R-010 (직전 6196.725ms, 30초 5건/60초 11건) | 1 | 0 |

## 판단

3초와 4초는 모두 request #12(R-012)에서 429가 시작됐다. 5초는 request #12(R-010)에서 단발 429가 발생했으나 재시도로 복구됐다. 각 429 직전 request-start 간격은 해당 설정값 이상이어서, 단순 start-spacing 위반만으로 설명할 수 없다.

P25-B2 기존 telemetry에는 prompt/context 크기와 API usage가 아직 기록되지 않아 token/resource quota를 판별할 수 없다. P25-B3 이후 새 실행에는 payload byte 수, context 문자 수, usage, 30/60/120초 요청량을 attempt마다 저장한다.

로컬 process 점검은 단일 실행 프로세스 외 동시 평가 스크립트를 확인하지 못했지만, 동일 credential이 다른 환경에서 사용되는지 여부는 로컬 telemetry로 증명할 수 없다. 전용 credential을 사용할 수 있다면 다음 6초 screen은 그 credential과 단일 프로세스로 실행해야 한다.

## 다음 gate

6초에서 10~15문항을 screen한다. 429가 한 번이라도 나오면 full run으로 승격하지 않고 provider quota/credential 격리를 우선 확인한다. 429=0인 경우에만 38문항 full sequential stability run을 검토한다.
