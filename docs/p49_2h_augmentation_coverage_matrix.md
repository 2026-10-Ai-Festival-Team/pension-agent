# P49-2H-2 Domain-Grounded Augmentation Coverage Matrix

This matrix fixes the **candidate-build plan**, not a training dataset.  The
600 targets are new candidate records; the frozen 36-record Robustness Human
Seed v1 is reference-only and is never overwritten or counted as augmentation
volume.

## Target distribution

| Outcome | Target | Purpose |
| --- | ---: | --- |
| `supported_answer` | 390 | Direct evidence exists; answer every required field faithfully. |
| `clarification_required` | 108 | Required user condition or referent is missing. |
| `bounded_answer` | 102 | The question is clear but one or more requested facts are not in the corpus. |
| **Total** | **600** | |

The complete question-type and domain quotas are stored in
`evaluation/fine_tuning/p49_2h_augmentation_coverage_matrix_v1.json` so they
can be checked mechanically before candidates are generated.

## Capability boundaries

- `Q16` and `D05`/`D10` remain in the deferred comparison lane: zero core
  candidates.
- `D06`, `D16`, and `D23` remain excluded until their canonical
  requirement-to-evidence mappings exist.
- `D29` is deterministic product-resolution provenance, not a Generator
  training domain.

## Mandatory high-risk coverage

- At least 60 records distinguish `product.total_fee` from
  `product.period_cost`.
- At least 50 records require complete table/row/column enumeration.
- At least 60 records test misconception correction and yes/no polarity.
- All 108 clarification records must ask only for the missing condition or
  referent.
- All 102 bounded records must retain supported portions and refuse only the
  unsupported requirement.
- At least 30 records must preserve explicit exclusion scope.

## Candidate promotion

Each candidate must retain `source_seed_id` provenance without copying or
modifying its seed.  The build sequence is:

```text
original corpus evidence
→ canonical requirement and outcome
→ question type
→ independent required gold facts
→ completion
→ evidence-first QA
→ human review
```

No candidate is a training example until P49-2I QA and human approval.  This
matrix does not authorize CLOVA tuning, Object Storage upload, or runtime model
changes.
