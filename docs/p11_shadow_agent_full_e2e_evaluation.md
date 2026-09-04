# P11: 전체 40문항 Shadow Agent 통합 사전 평가

## 목적과 통제

P10 experimental Router/route-specific gate, P5/P6의 compound evidence selection,
P8-B minimal citation representation을 production `PensionAgent`와 분리된 shadow
composition에 연결할 수 있는지 확인한다. 이 단계에서 production Agent, BM25,
normalizer, HCX-DASH-002, generation prompt, citation validator, Fail-Closed 정책은
변경하지 않았다.

P11은 먼저 HCX를 호출하지 않는 offline 라우팅·게이트 검사를 수행한다. non-P9
질문에서 의미 있는 안전성 회귀가 나오면, 그 run의 HCX 결과는 orchestration 효과와
일반화 실패를 구분할 수 없으므로 실제 40문항 호출을 하지 않는 것이 사전 고정된
운영 규칙이다.

## 라벨과 지표의 한계

`evaluation/p11_full40_routing_labels.json`에는 40문항의 수동 gold route와 P3의
기존 semantic retrieval-sufficiency 라벨을 결합했다. 기존 HCX 결과가 transport/
format 실패여서 P3 semantic 검토 대상이 아니었던 7개 answerable 질문은
`unknown`으로 남겼다. `unknown`을 evidence-insufficient로 추정하지 않았다.

따라서 다음을 구분한다.

- `direct_gold_hit`: 현재 Top-10에 exact direct gold `chunk_id`가 있는지의 기계적 신호
- `semantic_retrieval_sufficiency`: 기존 P3 수동 검토의 `full`/`partial`/`none`/`unknown`
- `false_rejection_known`: known `full`인데 Shadow gate가 HCX를 차단한 경우
- `unsafe_pass_known`: known `partial` 또는 `none`인데 Shadow gate가 HCX 호출을 허용한 경우

exact gold가 없어도 동등 근거가 있을 수 있으므로, `direct_gold_hit`만으로 unsafe
pass를 판정하지 않는다.

## Offline 결과

| Subset | Cases | Routing accuracy | Misrouted | False rejection (known) | Unsafe pass (known) | Unknown sufficiency | Expected HCX calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| P9 dev | 15 | 15/15 (100.0%) | 0 | 0 | 0 | 1 | 9 |
| Non-P9 | 25 | 21/25 (84.0%) | 4 | 1 | 1 | 6 | 24 |
| Full 40 | 40 | 36/40 (90.0%) | 4 | 1 | 1 | 7 | 33 |

P9 개발 부분집합에서는 P10 결과를 재현했다. 그러나 규칙을 설계할 때 사용하지 않은
25문항에서는 compound 4건이 simple로 잘못 라우팅됐다. 또한 full evidence가 있는
R-006은 requirement template이 없다는 이유만으로 차단됐고, partial evidence인
R-019는 simple route에서 통과했다.

| Case | Gold → Shadow route | Sufficiency | Gate result | Primary owner | 의미 |
|---|---|---|---|---|---|
| R-006 | compound → compound | full | reject: requirements not defined | requirement template/gate | 완결 가능한 compound를 template 공백 때문에 차단 |
| R-019 | simple → simple | partial | pass | gate | simple gate가 partial 근거를 충분으로 처리 |
| R-032 | compound → simple | full | pass | router | 복합 질의를 기존 simple 경로로 보냄 |
| R-033 | compound → simple | unknown | pass | router | P3 검토 불가 사례; HCX 전 재검토 필요 |
| R-034 | compound → simple | unknown | pass | router | P3 검토 불가 사례; HCX 전 재검토 필요 |
| R-036 | compound → simple | full | pass | router | 동등 근거는 있으나 복합 evidence 검증을 건너뜀 |

`R-012`, `R-016`, `R-017`, `R-024`, `R-033`, `R-034`, `R-035`는 prior semantic
sufficiency가 `unknown`이다. 이들은 안전 pass/reject 지표의 분모에서 제외했다.

## Baseline vs Shadow E2E

**실제 HCX E2E는 실행하지 않았다.** non-P9에서 4/25 routing error, known false
rejection 1건, known unsafe pass 1건이 확인돼 P11의 실제 호출 전 통과 조건을 충족하지
못했다. HCX 33회 예상 호출을 진행하면 새 Router/Gate의 일반화 실패와 provider/생성
품질을 한 결과에 섞게 된다.

따라서 아래 지표는 의도적으로 `not evaluated`다. 값을 0 또는 baseline과 동일하다고
기록하지 않는다.

| Metric | Baseline | Shadow | 상태 |
|---|---:|---:|---|
| API success | — | — | HCX E2E 미실행 |
| HCX Accepted Answer Rate | — | — | HCX E2E 미실행 |
| Citation exact copy / rejection | — | — | HCX E2E 미실행 |
| Semantic correctness | — | — | HCX E2E 미실행 |
| Requirement coverage | — | — | HCX E2E 미실행 |
| Strict End-to-End Useful Answer Rate | — | — | HCX E2E 미실행 |
| Mean / p95 latency, token usage | — | — | HCX E2E 미실행 |

기존 P8-B의 compound minimal citation representation과 P7의 R-037 success는 여전히
유효한 **국소 실험 결과**지만, 이 P11 전체 Shadow composition의 성능으로 일반화하지
않는다.

## 핵심 케이스

- R-002, R-011, R-028, R-037은 P9 subset에서 기존 P10 offline 결과와 일치했다.
  P11에서는 이 케이스들에 대해 새 HCX 호출을 하지 않았다.
- R-010, R-024, R-028, R-037은 compound gate가 계속 사전 차단하므로, partial/none
  evidence를 생성기로 넘기는 기존 unsafe path를 재도입하지 않았다.
- R-006은 새로운 generalization blocker다. gold route는 정확히 compound로 맞혔지만,
  P5 requirement case 목록에 없어서 완전한 근거가 있어도 `compound_requirements_not_defined`
  로 차단된다.
- R-032, R-033, R-034, R-036은 comparison/entity만으로 포착되지 않는 복합 요구를
  보여준다. 현재 Router는 이 표현군을 simple로 보낸다.

## 결정

**Needs refinement — production 통합 및 HCX full-40 run 보류.**

P10의 15/15는 P9 dev-oriented set에서만 확인된 결과였다. P11은 non-P9에서 라우터와
requirement template coverage의 일반화 공백을 확인했다. P11 결과를 보고 즉석에서
규칙을 수정하지 않았으며, 다음 작업은 별도 P12로 분리한다.

P12의 최소 범위는 다음과 같다.

1. non-P9 compound 4건과 R-006을 독립 검토해 gold route와 required slots를 확정한다.
2. requirement template coverage와 compound detection을 별도 development set에서 수정한다.
3. 수정 전후 non-P9 holdout을 다시 offline 평가한다.
4. false rejection과 unsafe pass가 해소된 뒤에만 Shadow HCX canary, 그 다음 full-40 E2E를
   같은 고정 조건으로 실행한다.

## 재현

```bash
PYTHONPATH="$PWD/.venv/lib/python3.9/site-packages" \
  python3 scripts/evaluate_p11_shadow_offline.py
```

결과는 Git 제외 경로 `data/diagnostics/p11_shadow_offline.json`에 저장된다. 이 artifact는
질문별 route, entity, required slot, evidence sufficiency, gate decision, 예상 HCX 호출,
그리고 E2E가 미실행임을 명시하는 placeholder 필드를 보존한다.
