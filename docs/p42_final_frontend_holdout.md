# P42 — Final Fresh Front-End Holdout

## Frozen evaluation boundary

P42 is the final fresh 18-question test of the isolated front-end path:

```text
resolver-first
  -> unique active subject only: subject-filtered selector enum
  -> factual-dimension precision instruction
  -> deterministic binder validation
  -> ambiguous scope: unresolved without HCX
```

It uses 14 selector-evaluable unique-scope questions and four safety-only
ambiguous-reference questions.  The candidate Agent, browser, retrieval,
evidence matcher, citation validator, and financial policy were not connected
or changed.

## Result

| Metric | Result | Gate |
| --- | ---: | ---: |
| Requirement precision | 95.65% | >= 95% |
| Requirement recall | 100.00% | >= 95% |
| Requirement exact | 13 / 14 (92.86%) | >= 90% |
| Multi-requirement recall | 16 / 16 (100.00%) | >= 95% |
| Final scope/reference accuracy | 14 / 14 | 0 errors |
| Ambiguous safe unresolved | 4 / 4 | 0 unsafe |
| Ambiguous unsafe resolution | 0 | 0 |
| Out-of-scope extra requirement | 0 | 0 |
| Binder scope expansion / binding error | 0 | 0 |
| Schema / ontology valid | 14 / 14 | 100% |
| Provider errors | 0 | 0 |

The four ambiguous forms (`그 상품`, `해당 계좌`, `이 제도`, `그 유형`) were
all blocked before HCX selection.  Ordinal and contrast references resolved to
the correct single scope before the filtered enum was constructed.

## Residual precision observation

P42-009 selected the two required education facts and one additional,
in-scope `DC.benefit_determination` requirement.  It is the only extra among
the 14 selector-evaluable rows.  It does not cross scope, does not cause a
binder error, and leaves precision above the pre-frozen 95% gate.  It is a
generation/selector precision backlog, not a reason to reopen the fresh
front-end gate.

## Decision

**P42: Fresh front-end Go.**  The pre-HCX scope/reference/requirement
selection layer satisfies its declared termination criteria.  Do not create
additional Pxx front-end holdouts or add new front-end rules from P42.

The next authorized step is **shadow integration**: run the frozen
resolver-first scoped selector alongside the existing candidate path without
changing browser behavior, then use a final fresh Closed E2E test to assess
retrieval, evidence sufficiency, citation, policy, and answer generation.

Raw result: `evaluation/p42_final_frontend_holdout.json`.
