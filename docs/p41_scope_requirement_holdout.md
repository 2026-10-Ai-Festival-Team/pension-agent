# P41 — Fresh Scope / Requirement Holdout

## Frozen scope

P41 is an 18-question fresh Closed factual holdout for the isolated
`scope/reference resolver -> frozen direct selector -> deterministic binder`
path.  The selector enum and prompt, candidate Agent, browser, retrieval,
matcher, citation contract, and financial policy were unchanged.  Each live
selector output was checkpointed before aggregation.

## Runtime and safety

| Check | Result |
| --- | ---: |
| Native Structured Output schema | 18 / 18 valid |
| Ontology validity | 18 / 18 valid |
| Unknown enum values | 0 |
| Provider errors | 0 |
| Ambiguous reference safe unresolved | 4 / 4 |
| Ambiguous unsafe resolution | 0 |
| HCX calls | 18 |
| Candidate/browser integration | none |

The P40-B generalized ambiguity rule held on all new ambiguous forms:
`해당 상품`, `해당 계좌`, `이 제도`, and `그 유형` were not bound to an
invented single subject.

## Requirement and final-scope result

| Metric | Result | P41 target |
| --- | ---: | ---: |
| Requirement precision | 87.5% | >= 95% |
| Requirement recall | 100% | >= 95% |
| Requirement exact | 15 / 18 (83.3%) | >= 90% |
| Multi-requirement recall | 20 / 20 (100%) | >= 95% |
| Final scope resolution accuracy | 12 / 14 (85.7%) | zero scope errors |
| Subject-requirement binding errors | 2 | 0 |

## Failure traces

### P41-008 — indirect DC scope over-selection

The question identifies the DC side through “가입자가 직접 운용방법을 정하는 쪽”,
then asks how that side's benefit is determined.  Gold is only
`DC.benefit_determination`; the selector returned both DB and DC benefit
requirements.  The binder correctly exposed two bound scopes rather than
silently choosing DC.

**Owner candidate:** `selector_scope_expansion` / indirect-subject semantic
miss.  This is not a resolver ambiguity failure because there is no singular
anaphora to resolve.

### P41-010 — ordinal account scope ignored by selector

The resolver deterministically resolves “두 번째 계좌” to IRP.  The selector
nevertheless returns both IRP and pension-savings withdrawal requirements.
The binder flags the pension-savings requirements as conflicts, so no unsafe
scope is accepted downstream.

**Owner candidate:** `selector_scope_expansion`; binder fail-closed behavior
is correct.

### P41-011 — unsupported related requirement

The education frequency/outsource question returns both required education
requirements plus unrelated `DC.operation_party`.

**Owner candidate:** `selector_extra_requirement`.

## Decision

**P41: No-Go for candidate shadow integration.**  The ambiguity resolver is
now fresh-holdout safe, and all requested multi-requirements were recalled.
However, the direct selector still over-selects requirements and can ignore an
already resolvable account/system scope.  P41 is now development/regression
data.  Do not modify the selector before a separate P41-A owner attribution;
do not claim P41 as a generalization pass or connect this path to the
candidate/browser.

Raw result: `evaluation/p41_scope_requirement_holdout.json`.
