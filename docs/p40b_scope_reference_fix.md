# P40-B — Generalized Singular-Anaphora Safety Rule

## Change boundary

The resolver now recognizes singular references across subject classes:
`그/이/해당 상품`, `그/이/해당 계좌`, `그/이/해당 제도`, and
`그/이/해당 유형`.

For each expression, it first restricts candidates to the compatible subject
class where possible.  It resolves only one candidate.  If two or more remain
and there is no ordinal, explicit name, or closed-pair contrast cue, it emits
`unresolved`.

The binder remains unchanged in responsibility: unresolved references return
only `unresolved_reference` bindings and never become comparison bindings.  A
single DC-scoped selector anchor may still bind an otherwise antecedent-less
`그 계좌`; it never adds a requirement.

## Regression contract

- P40-005 must be unresolved rather than a two-product comparison.
- Ordinal product/account references and `DB와 달리` must remain resolved.
- P40-009 selector-anchored binding must remain available.
- No requirement enum/prompt, candidate Agent, browser, retrieval, or HCX
  changes are allowed.

Result: `evaluation/p40b_scope_reference_regression.json`.

## Regression result

| Metric | Result |
| --- | ---: |
| HCX calls | 0 |
| Ambiguous-reference safe unresolved | 3 / 3 |
| Ambiguous unsafe resolution | 0 |
| Subject-requirement binding errors | 0 |
| Resolved-reference accuracy | 14 / 15 (93.33%) |
| P39-3C prototype acceptance | retained |

The remaining raw-resolver miss is P40-009, where the question supplies no
explicit account antecedent.  Its selector returns only DC-scoped requirements,
so the existing binder anchor safely yields DC without adding a requirement.
This is recorded as a resolver-observability limitation, not an unsafe scope
resolution.

**P40-B: regression Go.**  P40 itself remains development data.  Freeze this
prototype and use a new P41 scope/requirement holdout for the next
generalization decision.
