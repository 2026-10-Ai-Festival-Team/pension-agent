# P22: Controlled Conditional Shadow HCX E2E

## 목적

P21에서 P20의 provider incident와 semantic failure를 분리한 뒤, Router/Gate,
RequirementBuilder, retrieval, prompt, citation representation을 모두 동결한 채
conditional Shadow를 재실행했다. 목적은 실제 global pacing을 관측하면서 P16
baseline과 같은 38개 answerable denominator의 Strict E2E Useful을 다시 측정하는
것이다.

## P22-A: telemetry smoke

Full run 전에 simple·compound를 포함한 R-001, R-002, R-005, R-011, R-027,
R-036을 순차 호출했다.

| Metric | Result |
|---|---:|
| Request-start 최소 간격 | 2000.053 ms |
| 429 / Retry-After | 0 / 0 |
| Spacing policy | pass |

새 telemetry는 attempt마다 limiter wait, request start/end, 이전 request와의
start/end delta, HTTP status, numeric Retry-After, retry sleep, latency, final
outcome을 원문·인증정보 없이 기록했다.

## P22-B: controlled full-40

P19 shared preparation artifact와 P22 HCX 직전 state를 다시 비교한 결과
**40 / 40 parity**였다. P19에서 해결한 known false rejection 0과 known unsafe
pass 0도 동일 preparation path에서 유지됐다.

| Metric | P16 baseline | P20 | P22 controlled shadow |
|---|---:|---:|---:|
| Preparation parity | 해당 없음 | 40 / 40 | **40 / 40** |
| HCX attempted | 38 | 33 | 33 |
| Accepted answers | 31 | 18 | 27 |
| HTTP 429 attempts | 18 | 42 | 13 |
| Provider retry exhaustion | 6 포함 | 13 | 3 |
| JSON/schema failure | 1 | 1 | 1 |
| Citation rejection | 1 | 1 | 2 |
| Mean / p50 / p95 total latency | 3248 / 2382 / 7144 ms | 3549 / 3176 / 6210 ms | 2686 / 2019 / 6210 ms |

Full run의 최소 request-start delta는 **1998.197ms**였다. P22 spacing policy는
측정 clock 오차 5ms tolerance를 포함하므로 위반 0으로 판정했다. 즉 관측된
간격은 2초 정책 범위 내였다. 그럼에도 429가 13회 발생했으므로, 이번 결과는
provider quota가 request spacing만으로 완전히 결정되지 않는다는 증거다. numeric
`Retry-After` 헤더는 한 번도 제공되지 않았다.

429는 5개 질문에만 영향을 주었다. R-015와 R-036은 retry 후 회복했고,
R-033/R-034/R-035만 429 retry exhaustion으로 최종 실패했다.

## 새 answer-hash semantic review

P22의 수용 answer 27개는 P16/P20 label을 재사용하지 않고 새 answer hash와
현재 cited context로 검토했다.

| Metric | P16 baseline | P22 controlled shadow |
|---|---:|---:|
| Semantic correctness | 23 / 31 | 24 / 27 |
| Full requirement coverage | 23 / 31 | 23 / 27 |
| Fully grounded | 26 / 31 | 24 / 27 |
| Strict useful accepted answers | 20 | 23 |
| **Strict E2E Useful Answer Rate** | **20 / 38 (52.6%)** | **23 / 38 (60.5%)** |

Provider retry exhaustion만 제외한 diagnostic rate는 23/35 = 65.7%, 어느
attempt에도 429가 없던 보수적 subset은 22/33 = 66.7%다. 둘 다 provider
incident를 제거해 architecture를 진단하는 용도일 뿐, 공식 E2E 점수는 아니다.

정상 HCX·schema·citation 통과 후 strict useful가 아닌 케이스는 다음 네 건이다.

| ID | Remaining issue |
|---|---|
| R-011 | 과세 시점 대신 압류보호 근거를 선택 |
| R-013 | 무조건적인 IRP 이전 의무 결론 |
| R-015 | 납입 방법 대신 한도·세액공제만 답변 |
| R-027 | 표의 분류 체계를 예시 목록으로 바꿔 답변 |

이는 429와 별개의 generation/evidence-selection backlog다. P22 전에 해당 문제를
고치지 않았으므로 결과는 controlled run에서의 재현 관측으로만 사용한다.

## Compound subset

P16부터 등록한 11개 compound reference cohort에서 P22는 R-005/R-027/R-036 세
answer를 수용했고, strict useful은 R-005와 R-036의 **2건**이었다. baseline도
compound strict useful 2건이므로, 전체 Strict E2E 상승을 compound orchestration의
명확한 semantic 개선으로 과장할 수는 없다.

## 결정

**Conditional architecture: functional integration candidate. Production Go: 보류.**

긍정 근거:

- Preparation parity 40/40, known FR 0, known unsafe pass 0을 실제 HCX 경로에서 유지했다.
- Strict E2E Useful이 baseline 52.6%에서 **60.5%**로 상승했다.
- P20의 대규모 provider exhaustion 13건은 P22에서 3건으로 줄었다.

보류 근거:

- 429 retry exhaustion 0 목표를 달성하지 못했다(3건).
- compound strict useful이 baseline보다 증가하지 않았다.
- citation rejection 2건 및 정상 HCX 후 semantic failure 4건이 남았다.

따라서 다음 우선순위는 Router/Gate 재수정이 아니라 (1) provider quota를 견디는
운영 제어와 (2) 위 네 generation/evidence-selection 사례의 별도 원인 분석이다.
그 두 축을 해결하기 전 conditional path를 production default로 승격하지 않는다.

## 산출물

- Git 포함: `evaluation/p22_controlled_results.jsonl`,
  `evaluation/p22_semantic_labels.json`, `evaluation/p22_case_deltas.json`,
  `evaluation/p22_failure_attribution.json`
- Git 제외: raw HCX responses, answer/context packet, per-attempt diagnostic
  timing (`data/diagnostics/p22_*`)

P22 실행은 비용이 발생하므로 `--execute`를 명시해야 하며, full run은 P22-A smoke가
429 0·spacing pass일 때만 수행한다.
