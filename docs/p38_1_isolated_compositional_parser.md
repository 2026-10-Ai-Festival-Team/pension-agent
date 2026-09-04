# P38-1 — Isolated Compositional Parser

P38-1 evaluates a new front-end representation without importing it into the
candidate Agent.  It has no retrieval, policy, HCX, citation, or API calls.

```text
Raw question
  -> lexical cleanup (clear aliases only)
  -> subject / action / field / modifier atoms
  -> RequirementComposer
  -> canonical requirements
```

The development-only gold data is
`question_bank/development/semantic_atoms_v1.jsonl`.  Its 30 P36/P37 questions
are not a generalization claim.  The evaluator compares canonical **sets** so
atom and requirement order do not change a result; distinct ontology fields
remain distinct.

## Metrics

- subject, action, field, modifier: micro precision / recall / F1
- requirement composition: exact set equality per question

The initial feasibility gates are Subject F1 >= 0.90, Action F1 >= 0.90, Field
F1 >= 0.85, Modifier F1 >= 0.80, and Requirement exact >= 0.80.  Passing this
development test only permits a fresh semantic-atom mini-holdout (P38-2); it
does not permit candidate integration.

## Development baseline

The isolated v1 run reached 30/30 exact composition and 1.00 micro F1 for all
four atom types.  This is a **development feasibility result only** because
every source question came from P36/P37.  It is intentionally insufficient for
a generalization claim; P38-2 must use a new, frozen semantic-atom holdout.

## Safety boundary

`CompositionalParser` is an experiment module only.  It is not referenced by
`QueryAnalyzer`, `RequirementBuilder`, candidate preparation, or browser/API
routes.  The experiment never calls HCX.
