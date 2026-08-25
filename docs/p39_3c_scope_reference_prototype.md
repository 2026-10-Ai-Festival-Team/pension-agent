# P39-3C — Scope / Reference Resolver + Binder Prototype

## Scope

This is an isolated, zero-HCX prototype. It consumes only the frozen P39-3
selector selections and hashes. Candidate Agent, browser, retrieval, citation,
financial policy, and the P39 selector enum/prompt/schema remain unchanged.

## Development checks

| Check | Result |
| --- | --- |
| P39-3-001: `DB와 달리` closed-pair contrast resolves active subject to DC | pass |
| P39-3-001: conflicting `DB.benefit_determination` is detected | pass |
| P39-3-003: `그 계좌` is anchored to selected DC scope, but missing operation-party requirement is not added | pass |
| P39-3-003: `selector_multi_requirement_incomplete` is emitted | pass |
| P39-3-018: `뒤에 적은 상품` resolves only to `KR5114450222` | pass |
| Ambiguous `그 제도` with DB and DC antecedents | unresolved; no scope widening |
| HCX calls / candidate integration | 0 / none |

## Boundary preserved

The binder only binds a selected requirement to an already resolved subject,
or rejects the binding. It does not add `DC.operation_party` to P39-3-003.
That omission remains a selector completeness failure by design.

## Decision

**P39-3C prototype: development Go.** The resolver/binder responsibility is
now independently testable. It is not production-ready and does not turn
P39-3 into a generalization pass. Next, treat P39-3 as regression data and
create a fresh P40 scope/reference holdout before considering integration.

Result: `evaluation/p39_3c_scope_reference_prototype.json`.
