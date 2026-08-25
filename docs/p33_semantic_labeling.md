# P33-S: Fresh Holdout Semantic Labeling

P33 실행 결과의 answer hash를 고정한 뒤 수동 라벨링했다. 이 단계에서는 Agent 코드, prompt, retrieval, gate, policy, pacing을 변경하거나 HCX를 재호출하지 않았다.

- 실행 artifact: [`p33_holdout_execution.jsonl`](../evaluation/p33_holdout_execution.jsonl)
- 라벨 artifact: [`p33_semantic_labels.json`](../evaluation/p33_semantic_labels.json)
- 실행 SHA-256: `713ffa882527e251e09663986a207385b58650d31ca74454f7859cf58191160f`

## 운영 계약

- API: 25/25 HTTP 200
- HCX 호출: 13건, provider/schema/citation critical failure: 0
- 429 / 5xx / timeout / retry exhaustion: 0 / 0 / 0 / 0
- Native Structured Output과 citation validator failure: 0

## 의미 품질 결과

| 지표 | 결과 | P33 Go 기준 | 판정 |
|---|---:|---:|---|
| Strict E2E Useful | **6/22 (27.3%)** | ≥ 17/22 (75%) | 실패 |
| Semantic correctness | 6/22 | 참고 | - |
| Requirement full coverage | 6/22 | 참고 | - |
| Fully grounded | 7/22 | 참고 | - |
| False rejection | **7** | ≤ 1 | 실패 |
| Unsafe pass | **4** | 0 | 실패 |
| Unsupported policy correct | **0/3** | 3/3 | 실패 |
| Provider/schema/citation critical failure | **0** | 0 | 통과 |

`strict_useful`은 answerable 22문항만 분모로 사용했다. unsupported 3문항은 별도의 정책 행동으로 평가했다.

## 1차 실패 분포

| Primary owner | 문항 수 | 문항 |
|---|---:|---|
| planner_miss | 5 | P33-001, 004, 005, 007, 008 |
| matcher_miss | 1 | P33-015 |
| field_confusion | 1 | P33-012 |
| requirement_omission | 2 | P33-013, 014 |
| policy_false_reject | 3 | P33-016, 017, 018 |
| policy_unsafe_pass | 4 | P33-019, 020, 021, 022 |
| grounding_mismatch | 3 | P33-023, 024, 025 |

## 판정

**No-Go.** P33은 P32-B 이후에 새로 동결한 holdout이므로, 이 결과는 P31/P32-B에서 보였던 성능이 새 질문의 requirement 구성·policy behavior·source relevance로 일반화되지 않았음을 보여준다. 반면 provider, schema, citation은 모두 정상이라 실패를 운영 장애와 혼동하지 않는다.

P33은 이 라벨링 이후 개발/회귀셋으로 전환한다. 다음 작업은 코드 수정보다 먼저 owner별 failure attribution을 확정하고, 수정이 필요하면 새 holdout으로 다시 검증하는 것이다.
