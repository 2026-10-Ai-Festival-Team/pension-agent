# P33-C2 Closed Core Failure Attribution

## Scope

- HCX is not called; this runs the candidate Agent's shared `prepare()` path.
- Closed Core remains a development-only evidence certification benchmark.
- A primary owner is the first observable upstream failure, not a semantic answer label.

## Result

- Preparation-insufficient rows: **0/46**
- `planner_missing`: **0**
- `subject_resolution`: **0**
- `retrieval_missing`: **0**
- `matcher_missing`: **0**
- `source_mapping_only`: **0**
- DOC-ID provenance still unmapped: **0** rows

## Interpretation

The current insufficient set contains **0** `planner_missing` and **0** `subject_resolution` rows. These are upstream of retrieval: the affected rows have candidates, but no requirement plan or product subject identity that can safely bind the evidence.

The `DOC-*` values are not present in corpus metadata. They are reported as `unmapped`, never converted into a retrieval pass/fail signal. A static provenance bridge must be supplied or verified separately before document-level recall can be certified.
