# P39-3B — Scope / Reference Resolver and Deterministic Binder Design

## Decision

Keep the P39 direct requirement selector's enum, Native Structured Output
schema, prompt, and model settings frozen. Add a separately testable scope /
reference layer before it, then bind its output to the selector's factual
requirements deterministically.

```text
Raw question
  │
  ├─ 1. Scope / Reference Resolver
  │      explicit subjects · mentions · references · active subjects
  │
  ├─ 2. P39 Direct Requirement Selector (frozen)
  │      allowed canonical requirements only
  │
  └─ 3. Deterministic Binder
         active subject × selected requirement → scoped retrieval request
```

The resolver never adds factual requirements, retrieves evidence, writes an
answer, or changes the selector's enum/prompt.

## Resolver contract

```json
{
  "explicit_subjects": ["product:KR5114420022", "product:KR5114450222"],
  "subject_mentions": [
    {"subject": "product:KR5114420022", "order": 1, "source": "explicit_code"},
    {"subject": "product:KR5114450222", "order": 2, "source": "explicit_code"}
  ],
  "references": [
    {
      "expression": "뒤에 적은 상품",
      "kind": "ordinal_product_reference",
      "resolved_to": ["product:KR5114450222"],
      "confidence": "deterministic"
    }
  ],
  "active_subjects": ["product:KR5114450222"],
  "unresolved_references": []
}
```

Canonical subjects remain limited to account/system entities (`DB`, `DC`,
`IRP`, `연금저축`, `ISA`, general/pension account) and product codes. The
resolver must preserve the order of explicit product mentions; the existing
`resolve_product_codes()` set-only result is insufficient for ordinal
references.

## Resolution rules and confidence

| Family | Input | Resolution | Confidence |
| --- | --- | --- | --- |
| Explicit entity | `DB`, `IRP`, product code or approved alias | Its canonical subject | deterministic |
| Product ordinal | `앞의/첫 번째`, `뒤의/후자/두 번째` | Ordered explicit product mention | deterministic |
| Nearest anaphora | `그 계좌`, `그 제도`, `이 상품` | Nearest compatible preceding active subject | deterministic when one antecedent exists |
| Closed-pair contrast | `DB와 달리 … 어느 쪽` | Complement within the explicit closed pair `DB ↔ DC` | inferred_closed_pair |
| Ambiguous reference | More than one compatible antecedent | No active-subject narrowing | unresolved / fail closed |

`inferred_closed_pair` is allowed only for a closed, explicitly enumerated
pair. It cannot infer a financial fact or introduce a new requirement. The
binder must reject a conflict between this inferred scope and the selector's
scoped requirement labels.

## Binder contract

The binder validates scope compatibility and produces a retrieval-facing
binding. It does not interpret missing factual fields.

```json
{
  "active_subjects": ["DC"],
  "selected_requirements": ["DC.employer_contribution", "DC.operation_party"],
  "bindings": [
    {"subject": "DC", "requirement": "DC.employer_contribution", "status": "bound"},
    {"subject": "DC", "requirement": "DC.operation_party", "status": "bound"}
  ],
  "scope_conflicts": [],
  "unresolved": false
}
```

Rules:

- Account/system-scoped requirement labels must agree with `active_subjects`.
- Generic `product.*` requirements bind only to one resolved product when a
  singular reference narrows the active subject set.
- A plural comparison keeps all explicitly active products.
- A mismatch, ambiguous reference, or absent product identity returns an
  unresolved binding; it never broadens to all candidates or guesses a code.
- The binder cannot add a requirement missing from the selector output.

## P39-3 failure mapping

| Case | Resolver/binder role | Selector role |
| --- | --- | --- |
| P39-3-001 | Resolve the contrast target as DC under the closed DB/DC pair; reject DB-scoped conflict | Still must choose `DC.operation_party`; current output omitted it |
| P39-3-003 | Resolve `그 계좌` to the DC scope anchored by the selected contribution requirement | Still must choose the second `DC.operation_party` requirement |
| P39-3-018 | Deterministically map `뒤에 적은 상품` to the second explicit code | `product.risk_grade.current` is already correct |

## Important boundary: P39-3-003 cannot be repaired by binding

P39-3-003 proves a remaining selector multi-label omission. A resolver can
produce `active_subject=DC`, and a binder can report that the question's
operation-party clause is not covered, but neither may manufacture
`DC.operation_party`. Doing so would create an unmeasured second requirement
selector and violate the frozen-selector experiment.

Therefore P39-3B has two legitimate outcomes:

1. **Scope/reference success:** P39-3-001 and P39-3-018 resolve correctly;
   P39-3-003 is detected as an incomplete selector output and fails closed.
2. **Full 18/18 requirement success:** requires separately authorizing a
   selector/coverage-contract change after P39-3B. It cannot be claimed from a
   scope resolver alone.

## Development acceptance criteria

- P39-3 scope traces reproduce exactly with no HCX call.
- Ordinal product reference resolution is exact.
- Explicit, nearest-anaphora, closed-pair, and ambiguous-reference fixtures
  have explicit expected outcomes.
- Binder creates no requirement, no subject, and no product code.
- Selector enum/prompt/schema remain byte-for-byte unchanged.
- Existing P39-1 requirement score is unchanged when bindings are not used.
- P39-3-003 is surfaced as `selector_multi_requirement_incomplete`, not
  silently repaired.
- Candidate/browser/retrieval remain unconnected.

After this isolated development work, create a new fresh P40 holdout with
ordinal, anaphoric, closed-pair, and ambiguous-reference cases. Only a clean
P40 pass can justify shadow integration.
