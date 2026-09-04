# P33-C1: Source-Relevance Generalization

## Scope

- HCX 호출 없음. P33은 개발 회귀셋이며 fresh-holdout 점수를 주장하지 않는다.
- 상품 field에는 `subject + field + factual value`를 함께 요구하고, 일반 경고문은 field 근거를 대체하지 않도록 했다.
- 동일 주체의 전략·손실 슬롯은 한 original source 안에서만 선택하도록 했다.

## Result

- Exact manifest chunk overlap: **12/18**
- Manually adjudicated semantic equivalent: **6**
- Exact or equivalent source relevance: **18/18**
- Partial evidence: **0**
- Wrong scope: **0**

## Equivalence controls

Equivalence was accepted only after checking `subject + account/product/system scope + field/requirement + factual value/condition`. A common source path alone was not accepted.

## Decision

P33-C1 closes the 18-item P33 source-relevance audit. The separate 46-item Closed Core evidence certification remains a development regression and currently exposes broader planner/retrieval coverage gaps; P34 remains blocked until those gaps are addressed and independently revalidated.
