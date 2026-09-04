# P49-2H-3A Curated Evidence Pool

`P49-2H-3A` is an evidence curation gate, not a generation or training step.
Each pool row has a canonical requirement, exact original `source_id` and
`chunk_id`, exact corpus text, evidence type, numeric/table anchors, an
optional calculation contract, and field-specific exclusion constraints.

Run:

```bash
.venv/bin/python scripts/build_p49_2h_curated_evidence_pool.py
.venv/bin/python scripts/validate_p49_2h_curated_evidence_pool.py
```

The validator rejects opaque IDs, missing corpus chunks, hand-edited evidence,
source/type mismatches, missing declared anchors, and active-domain coverage
gaps. `D30` is `optional_context_only`: it can supply a real current fact in a
bounded answer but cannot serve as evidence for a future value.

For a `clarification_required` request, a direct pool row can be passed only as
optional context. It never supplies the missing user condition or changes the
clarification outcome.

The pool is not training data. It cannot call HCX, generate candidates,
promote human-review state, export training JSONL, or permit tuning. After its
audit passes, the next permitted operation is a separately stored 70-100
record pilot.
