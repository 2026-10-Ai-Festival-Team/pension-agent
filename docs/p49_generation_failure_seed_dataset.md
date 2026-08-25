# P49-1 Genuine Generation Failure Seeds

P49-1 extracted only manual labels whose failure owner is answer generation:
`generation_omission`, `generation_misread`, `generation_field_confusion`, or
the legacy-equivalent P45 owner `field_confusion`.

## Frozen provenance checks

For every extracted seed, the extractor verifies:

1. the semantic-label file names its frozen raw E2E result;
2. its `answer_hash` matches the corresponding raw output;
3. the raw run's canonical manifest hash matches the frozen manifest;
4. every manifest gold-evidence chunk was present in the frozen HCX context;
5. every copied evidence chunk exists in the corpus and is marked
   `original_primary`.

## Result

19 seed records were extracted. They are intentionally not training examples:
they contain no completion and have
`promotion_status=seed_only_manual_completion_required`.

| Failure family | Seeds |
| --- | ---: |
| required-field completeness | 4 |
| table/enumeration completeness | 7 |
| field distinction | 6 |
| evidence fidelity | 2 |

The complete machine-readable totals and frozen hashes are in
`evaluation/fine_tuning/p49_generation_failure_seed_summary.json`.

No tuning API was called. P49-2 must manually author positive and contrastive
records from different source documents and expressions, then verify all
completion claims and citation IDs against the exact input direct evidence.
