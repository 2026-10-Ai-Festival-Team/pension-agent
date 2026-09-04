# P47 Final Fresh Single-Subject Closed E2E

## Frozen run

- Manifest SHA-256: `dd11d361dac1dfcd89222d4ea5bc65ff78ad91c62f8edd06c20dfd6d0be4a086`
- Raw-result SHA-256: `f558dc5ad63bba3b8cf3331ab6da9d623a603b7f988542deedfa1d6ff29fc18c`
- Supported lane: answerable, resolved, single-active-subject Closed factual questions.
- Excluded boundary: genuine multi-subject comparison.
- No HCX recall or code change occurred after the raw result was frozen.

## Result

| Metric | P47 gate | Result |
| --- | ---: | ---: |
| Strict useful | >=85% | 14/18 (77.8%) |
| Requirement recall | >=95% | 94.4% |
| Requirement precision | >=95% | 94.4% |
| Subject/scope critical error | 0 | 1 |
| Gold direct-evidence coverage | >=95% | 17/18 (94.4%) |
| Wrong-scope evidence | 0 | 0 |
| Citation valid | 100% | 17/17 generated answers |
| Provider/schema critical error | 0 | 0 |

## Failure owner

| Owner | Cases | Count |
| --- | --- | ---: |
| Exclusive-scope resolution | P47-004 | 1 |
| Genuine generation omission | P47-008, P47-010, P47-014 | 3 |
| Retrieval/evidence | — | 0 |

P47-004 shows the remaining structural gap: `IRP는 빼고 연금저축 계좌에만` is an exclusion/only form that the resolver safely rejects rather than resolving to `pension_savings`. It is a false rejection, not a retrieval failure.

Each generation failure already had the exact direct gold evidence in its HCX context. The recurring failures are: change-possibility omission and omission of either a total-fee column or its annual-rate table identity.

## Decision

**No-Go for fine-tuning entry.** P47 does not meet the strict-useful, front-end, requirement, or direct-evidence gates. P47 is now a development regression set. Do not patch P47 in place and call its score generalization.

The next narrow work is to attribute and generalize the exclusive-scope connector family without weakening ambiguity safety, then validate on a new fresh E2E. Only after front-end/evidence failures are absent and the remaining failures are predominantly generation should fine-tuning begin.
