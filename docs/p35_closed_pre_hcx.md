# P35 Fresh Closed Factual Holdout — Pre-HCX

## Frozen scope

- Frozen manifest SHA-256: `bb8eda3bd2f76bf8798b2ab6b531fc0ce6856a656a7f6fcd046363650fd03ad7`
- HCX was not called; this result covers only shared preparation.
- P35 becomes a development set if this pre-HCX gate fails. Do not change code before declaring the result.

## Result

- Requirement-plan coverage: **13/18**
- Evidence sufficiency: **16/18**
- Selected evidence original + primary: **18/18**
- Exact gold source relevance: **11/18**
- Manual source-relevance reviews required: **6**
- Wrong scope: **0**

## Next gate

Review every non-exact selected chunk against subject, field, value/condition, and account/product/system scope. Only an 18/18 exact-or-equivalent result with no partial or wrong-scope evidence permits HCX E2E.
