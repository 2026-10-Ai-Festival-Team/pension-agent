# P40-A — Scope / Reference Attribution

## Scope

This is a read-only attribution of the frozen P40 output.  It makes no HCX
calls and changes neither the resolver nor the binder.

## Primary blocker: P40-005

| Layer | Observed behavior |
| --- | --- |
| Candidates | Two explicit products are present |
| Reference | The question uses singular `그 상품` |
| Disambiguating cue | None: no ordinal, `전자`, `후자`, or named product |
| Resolver | Does not register `그 상품` as an anaphora or unresolved reference |
| Binder | Emits a two-product `bound_comparison` binding |

**Primary owner: `ambiguity_detection_miss`.**  The current anaphora pattern
recognizes `그 계좌` and `그 제도`, but not `그 상품`.  The resulting comparison
binding is a downstream `binder_scope_expansion`, not the initiating defect.

The required generalized rule is:

```text
multiple compatible candidates
+ singular anaphora
+ no ordinal / explicit-name / other disambiguating cue
=> unresolved
```

It must apply consistently to product, account, system, and type references.
Once the resolver returns `unresolved`, the binder must preserve that failure
closed state and must not create a comparison binding.

## P40-009 metric clarification

The raw resolver leaves `그 계좌` unresolved because the question names no
explicit account.  The frozen selector selected only DC-scoped requirements,
and the binder then safely anchored both already selected requirements to DC.
It did not add a requirement.  This is therefore a **raw resolver antecedent
limitation**, but not a final binding safety failure.

## Decision

**P40-A: attribution complete.**  P40 remains a development/regression set
and candidate shadow integration remains prohibited.  The next bounded change
is P40-B: generalized singular-anaphora ambiguity detection in the resolver,
with the binder kept strictly fail-closed.

Result: `evaluation/p40a_scope_reference_attribution.json`.
