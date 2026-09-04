# P38-4 — Semantic Contract Diagnosis

## Boundary

P38-4 reuses the frozen P38-3 output artifact only. It makes no HCX calls and changes no candidate-Agent, retrieval, matcher, gate, citation, prompt, or financial-policy code.

The review asks whether each missing `action` or `modifier` is actually necessary for a factual retrieval requirement, rather than treating all atom-set mismatches as equal errors.

## Review categories

- `prompt_salience_miss`: the ontology atom is valid and essential, but HCX omitted it.
- `ontology_redundancy`: field or subject structure already preserves the atom's meaning.
- `ontology_granularity_mismatch`: the ontology cannot express the relationship at the right grain.
- `gold_contract_issue`: gold requires an atom that the frozen P38-3 enum cannot return.
- `semantic_inference_failure`: HCX emitted an atom with no support in the question.

## Result

See `evaluation/p38_4_semantic_contract_diagnosis.json`. The P38-3 `0/18` requirement-exact metric remains valid for the current composer contract, but P38-4 distinguishes redundant contract mismatches from genuine semantic losses before any ontology or prompt v2 decision.
