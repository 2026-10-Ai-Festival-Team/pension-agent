# P48 Final Fresh Single-Subject Closed E2E

## Frozen contract

- Manifest SHA-256: `d0894d03e8e7df7164d5ba8fd3e416ead0f42aadbf5ef3dc7f14daeabe89bff1`
- Raw-result SHA-256: `8feadb381d9942d5bd6e781d1e44ef23fa0398459201ee502459241a4b9398cf`
- The E2E contract passes `status`, `active_subject`, `selected_requirements`, and `allowed_requirements` together from the scoped selector to preparation. This was explicitly unit-tested before manifest freeze.
- No code or HCX recall occurred after raw-result freeze.

## Operational and front-end result

| Metric | Gate | Result |
| --- | ---: | ---: |
| Requirement recall | >=95% | 100% |
| Requirement precision | >=95% | 100% |
| Requirement exact | — | 18/18 |
| Scope critical error | 0 | 0 |
| Wrong-scope evidence | 0 | 0 |
| Direct gold-evidence coverage | >=95% | 18/18 |
| Provider/schema critical error | 0 | 0 |
| Citation valid | 100% | 18/18 |
| Strict useful | — | 11/18 (61.1%) |

## Failure ownership

| Owner | Count |
| --- | ---: |
| Front-end / scope | 0 |
| Retrieval / evidence | 0 |
| Generation omission | 4 |
| Generation misread | 2 |
| Generation field confusion | 1 |

Every strict failure had exact direct evidence in the HCX context and a valid primary citation. The recurrent output behaviors are:

- required factual field/condition omitted;
- table identity or required column omitted;
- total-fee field confused with a share-class label;
- evidence-faithful answer replaced with a different tax distinction or an unsupported implication.

## Decision

**Pre-finetuning orchestration Go.** This is not an answer-quality Go: strict useful remains 11/18. It is evidence that the remaining substantive failures in the supported single-subject Closed lane are generation-owned rather than resolver, selector, retrieval, evidence, citation, schema, or provider failures.

Freeze the single-subject front-end/retrieval path. The next phase is fine-tuning dataset design and an isolated tuned-vs-base evaluation, built from the P45–P48 generation-owned failure families. Do not use P48 itself as a post-tuning generalization score; it is now a development/regression set.
