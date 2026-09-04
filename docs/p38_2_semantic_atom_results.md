# P38-2 — Fresh Semantic-Atom Mini Holdout Result

## Frozen execution

- Manifest SHA-256: `a8f2c972c589dd012375fa422cb714e0695e0999349624171217abb946f2213e`
- Questions: 18
- Candidate-Agent changes: **none**
- Retrieval / HCX / citation / policy calls: **0**
- Parser: the already frozen P38-1 isolated compositional parser

## Result

| Metric | Result | Gate |
| --- | ---: | ---: |
| Subject F1 | 0.9474 | >= 0.90 |
| Action F1 | 0.7826 | >= 0.90 |
| Field F1 | 0.6809 | >= 0.85 |
| Modifier F1 | 0.6667 | >= 0.80 |
| Requirement exact | 4/18 = 0.2222 | >= 0.80 |

**Decision: No-Go.**  P38-1's 30/30 development result did not generalize to
new surface forms.  P38-2 is now development/regression material; it cannot
be used to claim generalization after any future parser change.

## Failure-family signal

The misses are concentrated before requirement composition:

- indirect withdrawal / required-document expressions: P38-2-002, 007, 018
- implicit contribution and account-comparison language: P38-2-004, 005, 006
- indirect ISA/financial-institution transfer expressions: P38-2-008, 009
- product-field paraphrases and temporal qualifiers: P38-2-012, 013, 015
- multi-field / modifier composition gaps: P38-2-001, 003, 017

This report does not propose a patch.  The next work is failure attribution and
redesign evidence, not candidate integration or phrase-rule expansion.
