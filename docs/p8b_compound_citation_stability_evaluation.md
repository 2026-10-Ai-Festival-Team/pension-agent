# P8-B: Compound Citation Stability 평가

## 목적

P8-A에서 성공한 minimal citation representation이 R-028·R-037만의 우연한 성공인지 확인했다. A(current)와 B(minimal)는 각 질문에서 **동일한 requirement별 retrieval·merged evidence set**을 사용하고, generation-facing citation 표현만 달리했다.

Production Agent는 변경하지 않았다.

## Subset과 실행 조건

- Subset: compound/compare/evidence-completeness 사례 9개 + single-evidence control 3개
- Core 반복 3회: R-002, R-011, R-028, R-037
- 기타 compound/control: 1회
- Negative: R-010, R-024는 generation 미호출
- Model: HCX-DASH-002
- 동일 corpus, Simple BM25, `pension-v1`, per-requirement retrieval, selected evidence, generation parameter, 2초 global limiter, retry, Fail-Closed, citation validator

세부 subset은 [p8b_compound_dev_subset.json](/Users/jun/Desktop/연금Agent대회/evaluation/p8b_compound_dev_subset.json), 초기 수동 semantic label은 [p8b_manual_semantic_labels.json](/Users/jun/Desktop/연금Agent대회/evaluation/p8b_manual_semantic_labels.json)에 있다. HCX 원문 응답과 joined semantic label이 포함된 reviewed run artifact는 Git 제외 진단 파일에 보관한다.

## Citation 안정성

| Representation | Citation-bearing generations | Full chunk ID pass | Citation Exact Copy Rate |
|---|---:|---:|---:|
| A current | 16 | 13 | 81.3% |
| B minimal | 16 | 16 | **100.0%** |

두 표현 모두 R-001에서 같은 structured-output failure가 1건씩 발생해 citation-bearing denominator에서 제외했다. 이 실패는 representation 차이가 아니라 provider output/schema 안정성 문제다.

R-028이 차이를 만들었다.

| Case | A current | B minimal | Case Stability Rate (B) |
|---|---:|---:|---:|
| R-002 | 3/3 citation·semantic 통과 | 3/3 통과 | 3/3 |
| R-011 | 3/3 통과 | 3/3 통과 | 3/3 |
| R-028 | **0/3**, source-prefix 인용으로 차단 | **3/3**, full chunk ID·semantic 답변 | 3/3 |
| R-037 | 3/3 통과 | 3/3 통과 | 3/3 |

R-028의 A/B는 selected evidence와 retrieval이 동일했다. 따라서 이 0/3 → 3/3 차이는 retrieval 개선이나 model 교체가 아니라 citation representation 차이에 귀속된다.

## Semantic quality 초기 검토

수용된 답변은 초기 수동 검토로 correctness, requirement coverage, grounding, relevance, hallucination을 분리했다. independent second review 전까지는 발표용 최종 수치가 아니다.

- B minimal은 core 4개에서 모든 반복이 direct·grounded·full coverage였다.
- R-027은 A가 분류명을 반복하는 수준으로 partial coverage였고, B는 표의 실제 분류 조건을 설명했다.
- R-028은 A가 citation validation을 통과하지 못해 semantic denominator에서 제외됐다. B는 same-product semantic equivalent 투자전략 표에 기반해 질문을 충족했다.
- R-037은 두 표현 모두 merged DB/DC 비교 표를 사용해 정확했다. 이는 이번 비교가 P7의 기존 Top-5 baseline이 아니라 **같은 merged evidence set 위의 citation representation 비교**이기 때문이다.

## Negative 및 control

| Case | 결과 | 해석 |
|---|---|---|
| R-010 | evidence incomplete → HCX 미호출 | expected Fail-Closed 유지 |
| R-024 | retrieval missing → HCX 미호출 | expected Fail-Closed 유지 |
| R-001 | A/B 모두 structured-output failure | representation과 독립된 provider/schema 안정성 backlog |
| R-004 | A/B 모두 “정보 없음” 답변 | requirement-specific retrieval/selection이 질문의 최소 부담금 근거를 잘못 선택한 별도 backlog |
| R-009 | A/B 모두 generation 전 차단 | 단순 세제 질의에 compound evidence gate를 적용한 false rejection; routing 대상이 아님 |

R-001·R-004·R-009은 B minimal의 regression이 아니다. 하지만 control 결과가 모두 정상이라고 볼 수 없으므로, 이를 무시하고 production integrate candidate라고 결론 내리지 않는다.

## Operational 결과

| Representation | 평균 prompt chars | 평균 accepted latency | 평균 accepted total tokens |
|---|---:|---:|---:|
| A current | 1,180 | 1,828ms | 596 |
| B minimal | 1,025 | 2,198ms | 593 |

minimal은 평균 prompt를 약 13% 줄였고 token 사용량은 사실상 동일했다. 이 작은 표본에서 latency는 B가 약 370ms 높았지만, representation 자체의 효과라고 일반화할 근거는 부족하다.

## P8-B 결론

**Needs refinement — conditional routing 설계 후보, production 구현 보류.**

minimal citation representation은 compound core subset에서 citation exact-copy rate와 R-028 case stability를 명확히 개선했다. 그러나 single-evidence control에서 드러난 schema failure·selection failure·false rejection은 routing 설계를 production에 넣기 전 분리 해결해야 한다.

### 후보 conditional routing (설계만)

```text
simple / single-evidence
→ 기존 retrieval + 기존 evidence policy

comparison / multi-topic / conditional
→ requirement decomposition
→ per-requirement retrieval
→ evidence completeness check
→ merged evidence
→ minimal citation representation
→ HCX + existing Fail-Closed validation
```

초기 routing 조건은 다음처럼 rule-based로 제한한다.

- 비교 의도 또는 둘 이상의 비교 entity
- 둘 이상의 independent required evidence slot
- 제도·세제처럼 둘 이상의 질문 요구가 결합된 경우
- 사용자 조건이 필요한 recommendation

R-024처럼 completeness가 false이면 HCX를 호출하지 않는다. R-009처럼 단순 질의를 compound gate에 넣지 않는다.

## 다음 우선순위

1. R-001 structured-output failure를 transport/schema 관측 backlog로 분리
2. R-004의 requirement-specific evidence selection 오류를 retrieval/slot rule로 분리
3. simple vs compound router의 dev-only unit·offline 테스트 설계
4. 그 뒤 conditional routing을 별도 branch에서 구현하고, 40문항 E2E로 검증
