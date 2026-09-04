# P35-B Generalized Closed Front-end Fix

## Scope

- HCX was not called.
- The frozen P35 manifest was not edited; its SHA-256 remains `bb8eda3bd2f76bf8798b2ab6b531fc0ce6856a656a7f6fcd046363650fd03ad7`.
- No question-ID branch, gold-chunk insertion, prompt change, or policy change was added.

## Changes

- A shared canonical normalizer maps bounded Korean surface forms into existing pension concepts before entity extraction and requirement planning: pension-savings abbreviations, colloquial intermediate withdrawal, proof documents, tax deferral, ISA maturity transfer, DB/DC operation party, and fixed-grade wording.
- Product factual slots add direct product-bound risk-grade anchors.  They require product identity and a grade-bearing factual statement, rather than accepting generic safety language.
- The selector ranks an explicit current risk-grade classification above historical change logs.
- Account-withdrawal slots require the applicable account terms in the chunk body, preventing a broad document title from making unrelated DC evidence satisfy pension-savings/IRP requirements.
- Semantic requirement revalidation records `risk_grade_changeability` separately from the basic risk-grade slot.

## P35-B shared-preparation result

| Metric | Result |
| --- | ---: |
| Semantic requirement coverage | **18/18** |
| Evidence sufficiency | **18/18** |
| Original + primary selected evidence | **18/18** |
| Exact gold evidence | 14/18 |
| Current semantic equivalent evidence | 4/18 |
| Exact or equivalent | **18/18** |
| Partial / wrong scope | **0 / 0** |
| HCX calls | **0** |

The four non-exact verdicts are bound to the current selected chunk IDs in
[`p35b_current_evidence_revalidation.json`](../evaluation/p35b_current_evidence_revalidation.json).
They must be re-adjudicated if selection changes.

## Regression

- P15 route/gate regressions: **0**
- P31 previously sufficient questions newly blocked: **0**
- P32 deterministic expected behavior: **25/25**
- P33 deterministic behavior: **25/25**; current source revalidation remains **18/18 exact-or-equivalent**
- Closed Core: **46/46 evidence sufficient**, product subject-field binding **10/10**
- Full pytest: **267 passed**

## Decision

**P35-B regression Go.** This closes the deterministic Closed front-end
regression only. P35 is already a development set, so it is not generalization
evidence. Freeze a non-overlapping P36 Closed holdout before making any further
code changes.
