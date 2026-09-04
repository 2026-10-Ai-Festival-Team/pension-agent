# P23: Provider Stability 및 Compound Failure Analysis

## 범위

P22 결과 이후 Router, RequirementBuilder, Gate, retrieval, generation prompt,
citation representation은 변경하지 않았다. P23은 다음 두 진단만 수행했다.

- **P23-A**: attempt-level telemetry가 실제 global request spacing을 기록하는지와
  2·3·4초 pacing의 소규모 provider 반응을 확인한다.
- **P23-B**: P22 compound cohort를 HCX 재호출 없이
  requirement → selected evidence → answer → semantic label 순서로 분류한다.

Git commit/push 및 production Agent 변경은 수행하지 않았다.

## P23-A: pacing smoke

동일한 simple·compound 6문항(R-001, R-002, R-005, R-011, R-027, R-036)을 단일
프로세스에서 순차 호출했다. 각 attempt에는 request start/end monotonic offset,
limiter wait, 이전 request delta, HTTP status, numeric Retry-After, retry sleep을
기록했다.

| Pacing | Questions | Observed min request-start delta | Spacing policy | 429 | Retry-After |
|---:|---:|---:|---|---:|---:|
| 2초 (P22-A) | 6 | 2000.053 ms | pass | 0 | 0 |
| 3초 | 6 | 2999.985 ms | pass | 0 | 0 |
| 4초 | 6 | 3999.990 ms | pass | 0 | 0 |

P22-B full-40에서는 2초 policy 범위 내 spacing(최소 1998.197ms, 측정 tolerance
5ms)을 지켰지만 429 attempt 13건, retry exhaustion 3건이 발생했다. 따라서 이번
P23 smoke는 **2·3·4초 모두 작은 표본에서 provider acceptance를 보였다**는 사실만
말해 준다. 3초나 4초를 full-40의 최소 안정점으로 확정하지 않는다.

현재 증거로 확정 가능한 결론은 다음과 같다.

1. P22/P23 telemetry는 limiter가 실제 request start 간격을 제어했는지 관측할 수 있다.
2. 2초 spacing을 지켜도 provider 429가 발생할 수 있다.
3. numeric `Retry-After`는 P22/P23에서 제공되지 않았으므로, provider가 직접 제시한
   backoff 기준은 아직 없다.
4. 최소 안정 pace를 결정하려면 provider 사용이 없는 cooldown 뒤 같은 full cohort를
   각 pace에서 반복해야 한다. 지금 추가 full-40을 실행하면 quota 상태를 다시 섞으므로
   수행하지 않았다.

## P23-B: P22 compound failure attribution

P22의 pre-registered compound reference cohort 11건을 분해했다.

| Failure type | Count | IDs |
|---|---:|---|
| strict useful | 2 | R-005, R-036 |
| retrieval missing | 3 | R-024, R-028, R-037 |
| evidence incomplete | 1 | R-010 |
| citation contract | 2 | R-002, R-006 |
| provider retry exhaustion | 2 | R-033, R-034 |
| generation misread | 1 | R-027 |

R-002/R-006은 required evidence가 selected context에 있었지만 HCX citation ID
계약에서 차단됐다. R-027은 분류 표가 선택됐지만 모델이 표의 분류 구조를 단순 예시
목록으로 축소했다. 이 두 종류는 “필요 근거가 없었다”가 아니라, HCX generation 또는
citation binding 후단의 문제다.

반대로 R-024/R-028/R-037은 generation 전 evidence slot이 완성되지 않았고, R-010은
필수 예외 근거가 불충분해서 gate가 안전하게 차단했다. 이들은 HCX 모델을 바꿔도
해결되지 않는 retrieval/evidence coverage backlog다.

## 판단

P22의 전체 Strict Useful 60.5%는 P16 baseline 52.6%보다 높고 P19 front-end
safety도 재현됐다. 그러나 P23은 다음 두 blocker를 확인했다.

1. **Provider**: 2초가 current provider 상태에서 full-40 안정점을 보장하지 않는다.
   3·4초 smoke 성공은 full-run 안정성 증명이 아니다.
2. **Compound semantic quality**: compound strict useful은 baseline 2건에서 늘지
   않았다. remaining cases는 provider·retrieval·citation·generation owner가 섞여 있다.

따라서 conditional architecture는 production candidate 상태를 유지하되 production
default 승격은 보류한다. 다음 개선은 Router/Gate 재튜닝이 아니라, provider-full-run
reliability protocol과 provider-clean R-002/R-006/R-027의 generation/citation 원인
분석을 분리해서 설계해야 한다.

## 산출물

- `evaluation/p23_rate_limit_smoke_summary.json`
- `evaluation/p23_compound_failure_analysis.json`
- `scripts/run_p22_controlled_hcx.py` (`--minimum-interval-seconds` 실험 override)
- `scripts/analyze_p23_compound_cases.py`

raw per-attempt timestamps, provider diagnostics, answer/context는
`data/diagnostics/`에만 저장하며 Git에서 제외한다.
