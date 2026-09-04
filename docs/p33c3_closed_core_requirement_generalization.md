# Closed Core Evidence Certification v1

## Scope

- Development-only 46-question factual benchmark; HCX is not called.
- Uses the same `prepare()` path as the candidate Agent.
- This verifies preparation-time evidence binding, not semantic answer quality.

## Result

- Evidence-sufficient preparation: **46/46**
- Selected evidence all original + primary: **46/46**
- Declared source-path recall: **16/23**
- Product subject-field binding (code-bound plans only): **8/8**
- Verified DOC-ID source recall: **3/3**
- Rows with unresolved DOC-ID provenance: **20**

## Interpretation

Only `verified` records in the separate DOC-ID bridge can contribute to automatic document-source recall. Unresolved IDs are neither source-recall passes nor retrieval failures. Product binding is measured only when the requirement plan is code-bound; `0/0` would mean an observability gap rather than a 0% score.

A source-path failure, incomplete gate, or subject-field binding failure is retained in the JSON artifact for diagnosis; this report does not relabel it as semantic equivalence automatically.

## P33-C3 Decision

- Closed Core preparation requirement coverage is **46/46** with no HCX call.
- P15/P31/P32 deterministic regressions remain zero; the P33 policy contract remains 25/25 and question-bank policy fixtures 6/6.
- P34 remains blocked: the separate P33 exact source-overlap checker is 12/18. Its six prior semantic-equivalence notes must be re-adjudicated against the *current* selected chunks; they must not be carried forward merely because a question ID matches.
- DOC-ID bridge remains an evaluation-metadata limitation: 3/24 verified mappings and 21 explicit unresolved records.
