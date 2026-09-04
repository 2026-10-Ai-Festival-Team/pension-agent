# P18: Full-40 Shared Shadow Preparation Parity

## 목적

P17에서 확인한 offline evaluator와 P16 Shadow의 composition 차이를 제거했다.
P18은 새로운 routing/gate evaluator를 만들지 않고, P16 Shadow Agent가 실제로 사용하는
`ConditionalRoutingShadowAgent.prepare()`를 Full-40의 유일한 preparation 경로로 실행한다.

동일한 입력에 대해 공용 `prepare_shadow_execution()` 직접 호출도 함께 실행해 다음 중간 상태가
40/40 동일한지 확인했다.

- route와 extracted entities
- dynamic requirement plan과 slots
- frozen BM25 original Top-10 및 expanded candidates
- gate decision / evidence sufficiency
- selected 또는 merged context IDs
- HCX 호출 예정 여부

HCX, prompt, Retriever, Corpus, static question-ID case, production `PensionAgent`는 사용하거나
변경하지 않았다.

## Parity 결과

| 항목 | 결과 |
|---|---:|
| Shared preparation parity | **40 / 40** |
| Route accuracy | 39 / 40 |
| Compound recall | 11 / 12 |
| Unsupported recall | 2 / 2 |
| Compound 중 dynamic requirement plan 생성 | 6 / 12 |
| HCX 호출 예정 | 32 / 40 |

따라서 이제 이 offline 결과는 P16 Shadow가 HCX 호출 직전에 실제로 사용하는 경로의
결정적 기준선이다. P12의 정적 question-ID registry는 P18 gate 입력과 성능 집계에 사용하지
않았다.

## 실제 dynamic baseline

| 정책 지표 | 결과 | 질문 |
|---|---:|---|
| Known false rejection | 4 | R-002, R-005, R-006, R-027 |
| Known unsafe pass | 2 | R-019, R-028 |

이는 P16에서 관측한 4/2와 일치한다. P18은 P16의 결과가 provider 변동이나 HCX 때문이
아니라, 현재 dynamic requirement composition의 실제 동작이라는 점을 확정한다.

compound 12건의 세부 상태는 다음과 같다.

| 상태 | 질문 |
|---|---|
| dynamic plan 없음 → `compound_requirements_not_defined` | R-002, R-005, R-006, R-010, R-027, R-037 |
| dynamic plan 생성·complete | R-024, R-028, R-033, R-034, R-036 |
| compound gold이나 simple으로 route miss | R-032 |

R-010/R-037의 reject는 prior retrieval sufficiency가 각각 `partial`/`none`이므로 안전한
Fail-Closed에 해당한다. 반면 R-002/R-005/R-006/R-027은 `full` 근거가 있어 dynamic plan
coverage 부족에 의한 false rejection이다. R-019는 simple fallback이 비어 있지 않은 context만
보고 통과했고, R-028은 product-field slot이 실제 투자대상·운용전략 근거보다 일반적이라
unsafe pass가 됐다.

## Gate decision 분포

| Gate decision | 건수 |
|---|---:|
| `simple_evidence_present` | 24 |
| `compound_requirements_not_defined` | 6 |
| `compound_requirements_complete` | 5 |
| `simple_requirements_complete` | 3 |
| `unsupported_or_personal_or_conditional` | 2 |

`compound_requirements_incomplete`이 0건인 점도 중요하다. 현재 병목은 gate가 known
insufficient evidence를 세밀하게 판별하는 단계보다, 동적 plan을 만들지 못해 Fail-Closed하거나
너무 일반적인 plan으로 complete 처리하는 requirement schema coverage다.

## 결정

**P18은 evaluation integrity gate를 통과했다.** 그러나 conditional Shadow를 production에
통합하거나 HCX E2E를 재실행하는 Go 조건은 아직 충족하지 못했다.

다음 작업은 Full-40 shared-path 기준선에서 확인된 dynamic RequirementBuilder의 coverage와
product-field evidence matcher를 진단하는 것이다. 다음 변경 전에도 static R-ID case를
production candidate의 입력으로 복사하거나, question-ID hardcoding으로 P18 수치를 올리면 안
된다.

HCX Shadow 재실행의 선행 조건은 shared-path Full-40에서 다음을 다시 만족하는 것이다.

```text
known false rejection ≈ 0
known unsafe pass = 0
route regression 없음
```

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p18_shared_shadow_preparation.py
```

결과 `data/diagnostics/p18_shared_shadow_preparation.json`은 원문 retrieval context를 포함할 수
있으므로 Git에서 제외한다.
