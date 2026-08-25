# P31-S: Full-40 Candidate 의미 품질 라벨링

P31에서 생성된 answer hash를 대상으로 새로 수동 라벨링했다. P27-E 결과를 재사용하지 않았으며, 같은 문항이라도 P31 hash가 달라지면 P31 답변을 다시 검토했다.

## 결과

- Strict E2E Useful: **32/38** (P27-E: 30/38)
- Semantic correctness: **32/38** (P27-E: 31/38)
- Requirement full coverage: **32/38**
- Fully grounded: **35/38**
- P27-E 동등 compound subset: **7/11** (P27-E: 7/11)
- P31 dynamic compound route: **9/15**
- P30 targets (R-011/R-034/R-035/R-038): **2/4** (P27-E: 0/4)

## P30 Target Delta

| ID | P27-E | P31 | 판정 |
|---|---|---|---|
| R-011 | answer irrelevance | strict useful | 개선 재현 |
| R-034 | numeric confusion | numeric confusion | P30-Live 개선 미재현 |
| R-035 | product-field confusion | strict useful | 개선 재현 |
| R-038 | answer irrelevance | partial | 관련 답변으로 개선됐지만 requirement 완결성 부족 |

## 해석

운영·형식 계약은 P31에서 모두 통과했다. P30는 Full-40에서도 Strict Useful을 30/38에서 32/38으로 올렸지만, 총보수와 기간별 비용 예시의 field 혼동(R-034)은 동일 evidence 아래서 재발했다. 따라서 P30 planner/product-field boundary는 candidate 효과가 있으나, product numerical generation을 완전히 해결한 것으로 보지 않는다.
