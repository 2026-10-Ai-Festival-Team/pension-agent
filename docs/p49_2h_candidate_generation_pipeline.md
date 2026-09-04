# P49-2H-3 Evidence-Grounded Candidate Generation & Validation

P49-2H creates **600 accepted records**, not 600 raw generations.  The raw
candidate plan is lane-specific to preserve clarification and bounded-answer
coverage during filtering:

| Outcome | Accepted target | Raw target |
| --- | ---: | ---: |
| `supported_answer` | 390 | 450 |
| `clarification_required` | 108 | 125 |
| `bounded_answer` | 102 | 125 |
| **Total** | **600** | **700** |

## Required lifecycle

```text
coverage matrix (frozen)
→ curated original-evidence pool
→ raw candidates by lane
→ deterministic validation
→ duplicate / leakage removal
→ quota reconciliation
→ human evidence-first review
→ accepted 600
→ frozen augmentation dataset
```

Every raw candidate starts as:

```json
{
  "generation_status": "generated",
  "validation_status": "pending",
  "human_review_status": "pending",
  "acceptance_status": "not_accepted"
}
```

Automatic validation may set only `validation_status`.  It must never approve
a record or promote it to accepted.

## Deterministic validators

1. **Provenance** — actual chunk IDs exist and copied evidence text exactly
   matches `data/parsed/chunks.jsonl`.
2. **Numeric/factual** — every required fact has literal evidence anchors.
   A result not printed in evidence is allowed only for an explicit,
   deterministic `percent_of` derivation whose base and rate are anchored in
   the selected evidence.
3. **Behavior policy** — requirement support states recompute to the declared
   `full`, `partial`, `none`, or `unresolved` evidence state and compatible
   outcome.
4. **Duplication/leakage** — normalized trigrams block near copies of another
   candidate or the frozen 36-record seed.
5. **Quota reconciliation** — each outcome lane is checked separately.

`total_fee`, `period_cost`, table enumeration, polarity correction, exclusion
scope, and bounded-answer behavior remain explicit quota families in the
frozen coverage matrix.  They are not delegated to a free-form judge.

## Invocation once a raw batch exists

```bash
python scripts/validate_p49_2h_augmentation_candidates.py \
  --input evaluation/fine_tuning/p49_2h_raw_candidates_v1.jsonl \
  --output evaluation/fine_tuning/p49_2h_validated_candidates_v1.jsonl \
  --manifest evaluation/fine_tuning/p49_2h_validation_manifest_v1.json \
  --full-batch
```

The command does not create training JSONL, upload artifacts, invoke a tuning
API, or change runtime behavior.
