# P41-B — Resolver-First Selector Precision Architecture Fix

## Isolated contract

P41-B does not connect to the candidate/browser and preserves the P39 full
catalog enum.  It adds a precision instruction plus an isolated, opt-in path:

```text
resolver
  -> exactly one active subject: subject-filtered requirement enum
  -> otherwise: unresolved_scope (no HCX call)
  -> selector with factual-dimension precision contract
  -> binder validates only; never adds a requirement
```

The filtered enum is enforced in the HCX Native Structured Output schema and
revalidated in application code.  A plural or unresolved subject never causes
the enum to be guessed or narrowed.

## P41 development regression

| Case | Result |
| --- | --- |
| P41-008 indirect DB/DC scope | `unresolved_scope`, HCX not called |
| P41-010 second account = IRP | only the two IRP requirements selected; pension-savings extras 0 |
| P41-011 DC education | only frequency and outsourcing selected; `DC.operation_party` extra 0 |
| Out-of-scope selected requirement | 0 |
| Binder-created requirement | 0 |
| Provider errors | 0 |
| HCX calls | 2 |
| Candidate/browser integration | none |

## Decision

**P41-B: development regression Go.**  This proves the two distinct controls
work on P41 development cases: unique scope limits the selector enum, and the
precision instruction suppresses a same-subject but unrequested requirement.
P41 is already development data, so this is not a generalization claim.

Freeze this experimental contract before the next and final fresh
scope/requirement gate.  The candidate/browser path remains unchanged.

Result: `evaluation/p41b_scoped_selector_regression.json`.
