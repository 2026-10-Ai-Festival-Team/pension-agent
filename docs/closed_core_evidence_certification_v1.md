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
