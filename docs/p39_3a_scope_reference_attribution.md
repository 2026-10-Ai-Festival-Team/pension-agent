# P39-3A — Scope / Reference Attribution

P39-3's three scope failures do not share one owner.

| Case | Primary owner | Evidence |
| --- | --- | --- |
| P39-3-001 | `subject_detection_miss` | Current deterministic detection finds only explicit DB. The selector infers DC for one field, but cannot complete the implied DC scope and independent operation-party request. |
| P39-3-003 | `multi_requirement_omission` | The selector chooses the correct DC contribution requirement, then drops the second, independently requested operation-party requirement after “그 계좌”. |
| P39-3-018 | `product_reference_resolution` | `product.risk_grade.current` is correct; the deterministic product resolver cannot turn “뒤에 적은 상품” into only the second explicitly named code. |

This confirms that the direct selector should not be discarded. Its factual
requirement selection is not the owner of the product-reference failure, and
only one of the two account cases is fundamentally a subject-detection
failure.

## P39-3B design boundary

Keep the direct requirement enum/schema/prompt frozen. Design a preceding,
independently testable scope/reference layer that emits only:

```text
explicit subjects
reference expressions
resolved subject subset
resolution confidence / unresolved
```

It must cover ordinal product references (`앞의`, `뒤의`, `첫 번째`, `두 번째`)
and anaphoric account/system references (`그 계좌`, `그 제도`) without adding
facts or requirements. The direct selector continues to choose factual
requirements; deterministic binding combines its selection with the resolved
scope. No P39-3-specific branch should be added.

Raw trace: `evaluation/p39_3a_scope_reference_attribution.json`.
