# P33-B: Generalized Orchestration / Policy Offline Regression

## Scope

- HCX 호출 없음. 이 결과는 semantic score나 일반화 성능을 주장하지 않는다.
- P32·P33은 failure attribution 이후 개발 회귀셋으로만 사용한다.
- Corpus, BM25 파라미터, HCX prompt/schema, citation validator, provider pacing은 변경하지 않았다.

## Results

- P15 route/gate regressions: **0**
- P31 previously-sufficient preparation regressions: **0**
- P32 deterministic regression: **25/25**
- P33 deterministic expected behavior: **25/25**
- P33 manifest-source overlap: **13/18**
- P33 first-turn policy wording: **7/7**
- Question bank fixture validity: **60/60**
- Question bank clarify/abstain policy fixtures: **6/6**

## Source-relevance diagnostic

The following P33 development cases did not contain a manifest-declared acceptable chunk in the selected context:

- `P33-003`
- `P33-013`
- `P33-023`
- `P33-024`
- `P33-025`

## Interpretation

The candidate now uses structural requirement plans (comparison axes, procedure/condition/benefit, account-specific tax and product-field boundaries) and policy predicates (clarify, personal account, external prediction, prompt injection). No question-ID branch was introduced.

`manifest-source overlap` is an exact check against P33's declared acceptable chunk IDs; it is stricter than later human semantic-equivalence adjudication. A mismatch is retained as a retrieval/selection regression candidate, not silently counted as a pass.

P33-B is an offline regression gate only. A new, non-overlapping P34 manifest may be frozen only after the declared source-relevance regression gate is resolved or adjudicated.
