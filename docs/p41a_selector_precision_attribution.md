# P41-A — Selector Scope / Precision Attribution

## Scope

This attribution reuses the frozen P41 output only.  It makes zero HCX calls
and changes neither the resolver, selector, binder, nor candidate Agent.

## Owner separation

| Case | Primary owner | What happened | What can address it |
| --- | --- | --- | --- |
| P41-008 | `selector_scope_expansion` | The indirect DC phrase led the selector to emit both DB and DC benefit requirements. | First teach the resolver this closed-pair predicate; only then can subject filtering safely narrow the selector enum. |
| P41-010 | `selector_scope_expansion` | Resolver correctly narrowed `두 번째 계좌` to IRP, but selector still emitted pension-savings requirements. | Run resolver first and expose only IRP-compatible scoped requirements to selector. |
| P41-011 | `selector_extra_requirement` | Selector added in-scope but unrequested `DC.operation_party` to education requirements. | An independent precision rule: select every requested factual dimension and no related dimensions. |

## Architectural implication

Scope restriction and precision must remain separate contracts:

```text
resolver
  -> active subject scope, or unresolved
  -> subject-filtered selector catalog
  -> exact factual-dimension selection
  -> binder validates only; never adds requirements
```

P41-010 demonstrates why resolver-first execution is useful: the resolver has
the deterministic IRP scope before HCX selection.  P41-008 demonstrates the
limit: filtering must not be introduced while the resolver has only plural
`DB/DC` candidates, because that would hide a missing indirect-subject
interpretation.  P41-011 demonstrates that catalog filtering cannot solve
in-scope extras.

## Decision

**P41-A: attribution complete.**  P41 remains a development set.  The next
work is a generalized selector-precision design, not per-question patches:

1. resolver-first subject scope where uniquely deterministic;
2. fail closed for unresolved scope;
3. independently enforce factual-dimension precision; and
4. preserve binder non-generation.

Result: `evaluation/p41a_selector_precision_attribution.json`.
