# P38-0 Compositional Canonicalizer Redesign

## Decision

P34--P37 repeatedly failed on unseen Closed factual phrasing before retrieval.
P37-A records 7 semantic-normalization failures, 4 product-field canonicalization failures, 1 account alias failure, and 1 multi-requirement omission.  The next parser must not expand a question-level phrase-to-intent dictionary.

## Target pipeline

```text
raw question
  → lexical normalization
  → semantic atoms: subject / action / field / modifier
  → requirement composition
  → deterministic schema validator
  → existing retrieval, matcher, gate
```

Lexical normalization remains limited to unambiguous abbreviations, spacing,
typos, and verified product aliases.  Semantic interpretation is represented
as atoms rather than as one global intent label.

## v1 ontology

| Layer | Examples |
| --- | --- |
| Subject | `account:DC`, `account:IRP`, `account:pension_savings`, `product:KR…` |
| Action | `contribute`, `withdraw`, `transfer`, `receive`, `manage`, `invest`, `compare`, `educate` |
| Field | `tax_credit_limit`, `tax_timing`, `withdrawal_reason`, `required_document`, `operation_party`, `risk_grade`, `total_fee`, `cost_example`, `tracking_index` |
| Modifier | `before_retirement`, `current`, `change_possibility`, `combined_limit`, `account_specific`, `comparison` |

The requirement composer must be able to create multiple factual requirements
from one question.  It must not choose one intent and discard the rest.

## Development specification

`question_bank/development/semantic_atoms_v1.jsonl` contains 30 manually
reviewed P36/P37 development questions.  Each row fixes the expected atoms
and composed requirements.  It is explicitly not a fresh holdout or a live
Agent input.

The component-level metrics to introduce before changing the live candidate
are:

- subject extraction accuracy
- action extraction accuracy
- field extraction accuracy
- modifier extraction accuracy
- composed-requirement exact/semantic coverage

## Non-goals

- no HCX call or prompt change
- no retrieval widening
- no matcher relaxation
- no question-ID branch
- no P37 score used as generalization evidence

## Next gate

Implement the compositional parser behind an experiment-only interface, score
it against `semantic_atoms_v1`, then run P34--P37 and Closed Core deterministic
regressions.  Only a new frozen holdout after that can establish generalization.
