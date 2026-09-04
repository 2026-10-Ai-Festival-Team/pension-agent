# P38-2 — Fresh Semantic-Atom Mini Holdout

P38-2 is an 18-question Closed factual semantic-decomposition holdout.  It
tests only:

```text
raw question -> isolated compositional parser -> atoms -> composer -> gold
```

It excludes candidate-Agent preparation, retrieval, HCX, citations, and policy.
The parser/composer must be frozen before the manifest is built and hashed.

## Fixed criteria

- Subject F1 >= 0.90
- Action F1 >= 0.90
- Field F1 >= 0.85
- Modifier F1 >= 0.80
- Requirement exact >= 0.80

Component order is ignored, but canonical ontology values are not synonyms at
evaluation time.  A failure in any semantic family must be reported separately,
even when the aggregate threshold passes.

P38-2 must not be used to modify the parser before its first result is fixed.
After result inspection it becomes development material; any later
generalization claim needs a new frozen semantic-atom holdout.
