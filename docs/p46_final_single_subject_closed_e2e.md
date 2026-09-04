# P46 Final Fresh Single-Subject Closed E2E

## Frozen run

- Supported lane: single active-subject Closed factual only.
- Genuine multi-subject comparison remains outside this experiment's frozen capability boundary.
- Manifest: `question_bank/holdouts/p46_final_single_subject_closed_e2e.jsonl`
- Manifest SHA-256: `497826ea123e96a58bb6c60cbc1cf123cfce3f3e36afa428a35b12fcd0eea649`
- Raw-result SHA-256: `3c7d72efbfa1730de4dd30e90345375c8c4d620116958c1a7d07e7ff8a5d9c97`
- No code or HCX recall was performed after the raw-result hash was fixed.

## Operational result

| Metric | Result |
| --- | ---: |
| Questions | 18 |
| Answer-generation HCX calls | 16 |
| Provider/schema failure | 0 |
| Citation-valid generated answers | 16/16 |
| Wrong-scope/product evidence | 0 |
| Ambiguous unsafe resolution | 0 |
| Mean answer-generation latency | 7.17s |

## Quality result

| Metric | P46 target | Result |
| --- | ---: | ---: |
| Requirement recall | >=95% | 88.9% |
| Requirement precision | >=95% | 87.0% |
| Requirement exact | — | 15/18 |
| Gold direct-evidence coverage | >=95% | 16/18 (88.9%) |
| Strict useful | >=85–90% | 13/18 (72.2%) |
| Subject/scope critical error | 0 | 1 |
| Provider/schema error | 0 | 0 |
| Citation validity | 100% | 16/16 |

## Failure ownership

P46 has five strict-useful failures.

| Owner | Cases | Count |
| --- | --- | ---: |
| Selector requirement miss | P46-003 | 1 |
| Subject-resolution miss | P46-010 | 1 |
| Genuine generation omission | P46-009, P46-013, P46-016 | 3 |

`P46-017` is additionally a non-semantic selector-precision regression: `product.period_cost` was selected but neither needed nor used in the final answer. It lowers front-end precision, despite a correct final answer.

All three generation omissions had the exact direct gold chunk in the HCX context. They are valid future fine-tuning candidates, but the two false rejections and selector extra requirement mean P46 is **No-Go** for fine-tuning entry.

## Decision

P46 does not meet the frozen front-end or strict-useful gates. Do not treat the generation failures as sufficient evidence to begin fine-tuning yet.

The next work must be failure attribution-led and restricted to the remaining front-end behavior:

1. indirect DB benefit-calculation requirement selection;
2. explicit product-code resolution under the current/change-possibility form;
3. selector precision for unrelated same-subject requirements.

After generalized fixes and deterministic regression, evaluate a new fresh single-subject Closed E2E holdout. Only when front-end/evidence failures are absent and generation failures remain the dominant owner should fine-tuning start.
