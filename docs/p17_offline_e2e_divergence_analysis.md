# P17: Offline↔E2E Divergence Analysis

## 목적과 범위

P15 offline 결과의 false rejection 0 / unsafe pass 0과 P16 실제 conditional
Shadow E2E의 false rejection 4 / unsafe pass 2가 왜 달라졌는지 분석했다. 이번
작업은 진단만 수행하며 Router, requirement rule, BM25, prompt, validator, HCX 설정,
production `PensionAgent`는 변경하지 않았다. HCX도 다시 호출하지 않았다.

대상은 P16에서 policy reference 기준으로 문제가 된 6개다.

- false rejection: R-002, R-005, R-006, R-027
- unsafe pass: R-019, R-028

각 질문에 대해 P12 full-40 static offline composition, P16 Shadow와 동일한
generation 전 replay, 저장된 P16 실행 결과, answer-hash semantic review를 하나의
machine-readable record로 비교했다.

## 핵심 결과

| 검증 항목 | 결과 |
|---|---:|
| 대상 6건이 P15 H/M 평가 세트에 포함됐는가 | 0 / 6 |
| P12 static offline과 P16 Shadow의 gate 호출 결론 차이 | 6 / 6 |
| 현재 Shadow helper replay와 저장된 P16 route/gate/context 일치 | 6 / 6 |
| static offline과 Shadow replay의 frozen BM25 original Top-10 일치 | 6 / 6 |
| primary owner | shadow integration 6 / 6 |

즉 `P15 0/0 → P16 4/2`는 같은 6개 R 질문에서 일어난 online regression이 아니다.
P15는 `H-001..H-020`, `M-001..M-012`만 평가했고 R-series full-40 6건은 평가하지
않았다. 가장 가까운 full-40 offline reference는 P12이며, P12와 P16은 같은 gate를
호출하더라도 **서로 다른 requirement composition**을 사용했다.

## Composition 차이

```text
P12 full-40 offline
question_id
→ p12_requirement_cases.json의 정적·수동 case
→ original BM25 Top-10
→ ExperimentalRouteGate

P16 conditional Shadow
question
→ ExperimentalRouter + 동적 RequirementBuilder
→ original BM25 Top-10
→ (동적 case가 있을 때만 requirement candidate expansion)
→ ExperimentalRouteGate
```

P16은 P12 정적 registry를 주입하지 않았다. Router가 `compound`로 판단했더라도
동적 builder가 해당 문장 형태에 대한 slot을 만들지 못하면 `requirement_case=None`으로
gate에 들어가며, 결과는 `compound_requirements_not_defined`가 된다. 반대로 simple로
떨어지면 정적 requirement가 없어서 `simple_evidence_present`가 비어 있지 않은 context만
보고 통과시킬 수 있다.

P17에서 `ConditionalRoutingShadowAgent.prepare()`를 공용 generation 전 helper로 추출했다.
Agent와 P17 진단 모두 이 helper를 사용하므로, 이후 offline parity 검증이 Shadow runtime과
다른 composition을 재구현하지 않는다.

## 케이스별 원인

| ID | P12 static offline | P16 Shadow replay | P16 실제 결과 | primary owner |
|---|---|---|---|---|
| R-002 | DB/DC 급여 산정 static slot complete → call | 동적 plan 없음 → `compound_requirements_not_defined` | HCX 미호출, false rejection | shadow integration |
| R-005 | 퇴직금/퇴직연금 지급 static slot complete → call | 동적 plan 없음 → reject | HCX 미호출, false rejection | shadow integration |
| R-006 | 제도전환/규약동의 static slot complete → call | 동적 plan 없음 → reject | HCX 미호출, false rejection | shadow integration |
| R-019 | DC 중도인출 법정사유 static slot incomplete → reject | 동적 plan 없음, simple fallback → `simple_evidence_present` | HCX 호출, unsafe pass | shadow integration |
| R-027 | 원리금보장/채권형 static slot complete → call | 동적 plan 없음 → reject | HCX 미호출, false rejection | shadow integration |
| R-028 | 투자대상/전략 static slot incomplete → reject | generic product-field dynamic slot complete → pass | HCX 호출, semantic error | shadow integration |

R-028은 특히 static case가 실제 투자대상·운용전략 표현을 요구한 반면, dynamic
product-field slot은 상품코드와 필드명 수준의 lexical match만으로 complete가 됐다.
따라서 citation validity와 별개로 evidence relevance·requirement coverage가 부족한
answer가 통과할 수 있었다.

## 배제된 가설

### Retrieval nondeterminism / context difference

배제했다. 동일 frozen retriever의 original Top-10이 6건 모두 static offline과 Shadow
replay에서 동일했고, replay의 route·gate decision·merged context·HCX 호출 여부도 저장된
P16 기록과 6/6 일치했다.

### Route integration bug

Router의 route 자체가 P16 기록과 replay에서 다르지 않았다. 문제는 route 뒤에 어떤
requirement case를 연결했는지다. 따라서 router rule 단독 문제가 아니라
**requirement registry ↔ dynamic builder ↔ gate의 integration parity 문제**다.

### HCX-driven secondary effect

false rejection 4건은 HCX 호출 전 발생했으므로 HCX 품질 원인이 아니다. unsafe pass
R-019/R-028 중 R-028의 semantic error는 generation 단계에서도 확인됐지만, 우선 원인은
부족한 evidence를 통과시킨 pre-generation composition이다.

## 결론

**P16 No-Go 결정은 유지한다.** 다만 P17은 다음 우선순위를 명확히 한다.

1. P12의 question-ID별 static registry와 P16의 동적 builder를 같은 시스템으로 간주하면 안 된다.
2. 다음 개선 전에는 full-40 offline 평가가 실제 Shadow와 같은 `prepare()` helper를 사용해야 한다.
3. dynamic requirement plan이 없는 compound는 안전하게 reject하는 현재 Fail-Closed는 유지한다.
4. 단, static case를 그대로 production에 복사하거나 R-ID hardcoding을 하는 것은 금지한다.
   다음 단계는 동적 requirement schema의 coverage와 product-field semantic matcher를 별도
   진단하는 일이어야 한다.
5. helper 기반 full-40 parity 평가에서 false rejection과 unsafe pass가 다시 0에 근접하는 것을
   확인하기 전에는 HCX Shadow E2E를 재실행하지 않는다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/analyze_p17_offline_e2e_divergence.py
```

출력 `data/diagnostics/p17_offline_e2e_divergence.json`은 원문 context와 P16 answer review를
포함하므로 Git에서 제외한다.
