# P49-0 Fine-tuning Contract Freeze

## Fixed learning boundary

Only the **final answer generator** is a training candidate. The P48 resolver, scoped requirement selector, binder, retrieval, direct-field evidence binding, evidence gate, citation validator, and financial policy are frozen inputs to this phase.

The generator receives:

```text
question + selected canonical requirements + original-primary direct evidence
```

It must return the existing user-visible form:

```text
[답변] ...
[근거] ...
[유의사항] ...
```

The existing application citation validator remains authoritative. Native/provider tuning data may not relax citation IDs, introduce unsupported facts, or make the generator repair resolver/retrieval errors.

## Canonical record

The provider-neutral schema is [p49_canonical_training_record_schema.json](../evaluation/fine_tuning/p49_canonical_training_record_schema.json). It is intentionally separate from any CLOVA Studio upload shape.

Every promotable training example requires:

1. every required fact in its completion;
2. every factual claim supported by input direct evidence;
3. a completion field consistent with selected canonical requirements;
4. no unrelated factual field;
5. expected cited chunk IDs present in the input context.

## P49-1 seed policy

`p49_generation_failure_seeds.jsonl` contains only frozen P45–P48 cases whose manual owner is `generation_omission`, `generation_misread`, or `generation_field_confusion`, and whose manifest gold chunk was actually in the HCX context.

Seeds are **not** training examples. They have no completion target and cannot be uploaded. Each seed must first produce manually authored positive and contrastive examples from different documents and expressions, then pass P49-2 Dataset QA.

The fixed families are:

- `required_field_completeness`
- `table_enumeration_completeness`
- `field_distinction`
- `evidence_fidelity`

## Later evaluation order

1. P49-2 Dataset QA;
2. P49-3 frozen generation regression: HCX-007 vs untuned HCX-005;
3. P49-4 tuned HCX-005 comparison;
4. P50 completely fresh E2E. P45–P48 cannot be used as post-tuning generalization evidence.

No tuning API call is authorized by P49-0/P49-1.
