# P45 Final Fresh Single-Subject Closed E2E

## 범위와 동결

P45는 비교 기능을 점수에서 제외해 숨긴 평가가 아니다. 현재 `ResolverFirstScopedSelector`가 의도적으로 `non_unique_active_subject → unresolved`로 동작하는 capability boundary를 명시한 별도 lane이다.

- 지원 범위: active subject가 하나로 확정되는 Closed factual 질문, 명확한 ordinal reference, single-subject multi-requirement
- 제외 범위: DB/DC·연금저축/IRP·상품 A/B의 양쪽 사실을 동시에 답해야 하는 genuine comparison
- manifest: `question_bank/holdouts/p45_final_single_subject_closed_e2e.jsonl`
- manifest SHA-256: `e16da8b9b70b86432663de18188e5b5416f7d4b4af0299790b41e107ed446810`
- 코드/manifest 검증 후 실행했으며, answer hash를 고정한 뒤 semantic labeling 동안 HCX를 재호출하지 않았다.

## 실행 경로

```text
Question
→ Scope / Reference Resolver
→ subject-filtered Direct Requirement Selector
→ Binder
→ resolved-scope retrieval
→ direct-field evidence binding
→ evidence gate
→ HCX-007 answer generation
→ strict citation validation
→ financial answer policy
```

selector와 answer는 하나의 global 6초 request-start limiter를 공유했다. browser 및 기존 candidate 경로는 변경하지 않았다.

## 운영 결과

| 항목 | 결과 |
|---|---:|
| 질문 | 18 |
| HCX answer 호출 / 성공 | 16 / 16 |
| provider·schema 실패 | 0 |
| citation valid | 16 / 16 |
| answer hash 고정 | 18 / 18 |
| 평균 answer generation latency | 7,098ms |
| 최대 answer generation latency | 9,563ms |

## Semantic labeling 결과

| 지표 | 결과 |
|---|---:|
| Strict Useful | 10/18 = 55.6% |
| semantic correct / partial / incorrect | 10 / 6 / 2 |
| front-end requirement exact | 16/18 |
| front-end requirement recall·precision | 88.9% / 88.9% |
| scope/reference critical error | 2 |
| required evidence coverage | 16/18 |
| wrong-scope/product evidence | 0 |

P45는 **No-Go**다. strict useful 목표(85–90% 권장)와 front-end requirement recall 목표(95%)를 모두 충족하지 못했다.

## Failure attribution

| Owner | 건수 | 사례 |
|---|---:|---|
| subject resolution | 1 | `확정기여형`을 DC로 canonicalize하지 못해 사전 차단 |
| scope resolution | 1 | `IRP를 함께 쓰지 않고 연금저축만`에서 부정된 IRP를 active scope에서 제외하지 못함 |
| generation requirement omission | 3 | 총보수 항목·기간별 비용 표·DB 산식의 핵심 dimension을 끝까지 답하지 않음 |
| field confusion | 2 | 총보수·비용 항목을 행/구성 보수로 바꿈 |
| generation misread | 1 | 기간별 열을 나열하지 않고 `몇 년 단위`로 축약 |
P45-A trace 재검증 결과, 위 비용 계열 및 DB 산식의 six answer failures는 exact gold direct evidence가 HCX 입력 context에 있었던 genuine generation failure였다. 따라서 `direct_field_evidence`와 `evidence_incomplete` owner는 P45에서 0건으로 정정한다.

따라서 이번 결과는 파인튜닝 필요성을 바로 주장하는 결과가 아니다. single-subject lane에서도 resolver/scope의 구조적 실패가 2건 남아 있다. 다만 앞단 수정 후에도 보존해야 할 첫 genuine generation candidate examples는 6건으로 확정됐다. P45는 이제 development/regression set으로 전환하며, 수정 후 일반화 주장은 새 fresh E2E holdout에서만 할 수 있다.

## 산출물

- raw run: `evaluation/p45_final_single_subject_closed_e2e.json`
- frozen checkpoint: `evaluation/.p45_final_single_subject_closed_e2e_checkpoint.jsonl`
- manual labels: `evaluation/p45_final_single_subject_closed_e2e_semantic_labels.json`
- P45-A attribution: `evaluation/p45_final_single_subject_failure_attribution.json`
