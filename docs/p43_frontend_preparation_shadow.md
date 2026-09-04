# P43 — Front-End Preparation Shadow

## Boundary

P43 replayed the frozen P42 front-end outputs beside the existing P27-D
candidate preparation path.  It performs retrieval and context comparison
only: no HCX call, answer generation, browser behavior, or candidate mutation
occurred.

## Result

| Check | Result |
| --- | ---: |
| P42 front-end prepared | 14 |
| Expected unresolved scope | 4 |
| Front-end contract error | 0 |
| HCX calls | 0 |
| Candidate/browser changes | 0 / 0 |
| Exact ordered context-list divergence | 18 / 18 |
| Prepared rows with any context overlap | 9 / 14 |
| Prepared rows with no context overlap | 5 / 14 |

Exact context-list divergence is not itself a failure: the legacy path can
return five contexts, while the front-end shadow collects at most two per
selected requirement.  However, the no-overlap rows require source-relevance
review before the new path can be considered for E2E.

## Structural blocker found

The shadow retrieval query concatenated the original question with the active
subject and requirement label.  For product questions containing several
product codes, the original question still exposed non-target product codes to
BM25.  This allowed contexts for an earlier/later non-active product to rank
for a requirement already narrowed by the resolver.

This is a **retrieval query scope contamination** issue, not a resolver,
selector, or binder regression.  The P42 front-end decision remains frozen.

## P43-B — Resolved-Scope Retrieval Query

The shadow query is now constructed solely from the resolver's active subject
and the selected canonical requirement.  The raw question is deliberately not
appended.  For product risk-grade fields, the existing direct,
product-code-bound evidence anchor is also included; BM25 itself is unchanged.
All product BM25 candidates are filtered to the resolved product code before
they enter the context.

| Check | P43-A | P43-B |
| --- | ---: | ---: |
| Product scope contamination | 3 | **0** |
| Expected unresolved scope | 4 | 4 |
| Front-end contract errors | 0 | 0 |
| HCX calls | 0 | 0 |
| Candidate/browser changes | 0 / 0 | 0 / 0 |

The two remaining no-overlap rows are not failures: P42-006 has direct
`연금저축` withdrawal/tax evidence and P42-007 has direct DC withdrawal
reason/document evidence.  Their chunks differ from the legacy contexts but
are semantic equivalents for the required facts.

## P43-C — Direct Field Evidence Binding

P43-C adds an isolated, requirement-specific direct-field filter to the
shadow.  It uses canonical field signals rather than question IDs, product
names, or document IDs.  A direct requirement now returns no candidate when
the retrieved original/primary text does not state that factual field.

| Canonical requirement | Direct field signal | Indirect evidence excluded | Result |
| --- | --- | --- | --- |
| `product.total_fee` | annual payment-rate + total-fee field | period-cost / KRW 10m investment example | direct annual fee table selected |
| `retirement_income.IRP_transfer.tax_timing` | retirement-income/deferral + pension-receipt taxation | transfer route or transfer eligibility alone | direct tax-timing table selected |

P42-002 now selects the product's annual total-fee table (`0.95`, `0.625`,
etc.), rather than the investment-period cost example.  P42-014 now selects
original/primary tables that state deferred retirement-income taxation at
pension receipt.  If either signal had no direct match, the result would be an
empty candidate set rather than an indirect-evidence pass.

## Decision

**P43-C: frozen preparation shadow Go.**  Product scope contamination remains
zero; ambiguous scope remains unretrieved; both previously missing direct
fields are now present; and no candidate, browser, HCX, or BM25 algorithm was
changed.  P42 remains a development regression set, so this does not claim
generalization.  The next step is read-only shadow integration, followed by a
new Fresh Closed E2E holdout only if that integration preserves this contract.

Results: `evaluation/p43_frontend_preparation_shadow.json` and
`evaluation/p43a_frontend_context_attribution.json`.
