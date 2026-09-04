# P38-3 — Isolated HCX-007 Structured Semantic Planner

## Purpose

Test whether HCX-007 can extract multiple semantic atoms from a Korean closed-factual question more reliably than the deterministic P38 parser. This is a feasibility experiment on the already-exposed P38-2 development set, not a generalization result.

## Fixed boundary

`raw question -> explicit lexical normalization -> HCX semantic atoms -> local ontology validator -> existing RequirementComposer`

- No candidate-Agent imports or modifications.
- No retrieval context, evidence selection, answer generation, citations, or financial-policy execution.
- Native Structured Outputs with `thinking.effort = none`.
- The API schema and the local validator both constrain output to the P38 ontology.
- Lexical normalization covers only unambiguous account aliases and product-code casing. It does not map semantic phrases to actions or fields.
- P38-2 remains developer data; its manifest SHA is checked before the run.

## Metrics

- Subject/action/field/modifier precision, recall, F1.
- Requirement exact accuracy after the unchanged deterministic composer.
- Multi-atom field recall.
- Schema validity, ontology validity, unknown values, missing atoms, extra atoms, and provider errors.

## Run

```bash
.venv/bin/python scripts/run_p38_3_hcx_semantic_planner.py --execute
```

The runner uses the configured HCX-007 endpoint and a 6-second global request-start interval. It stores atom outputs and response hashes/telemetry only; raw HCX text is not persisted.

## Decision boundary

P38-3 is feasible only if schema validity is 100%, unknown ontology values are 0, and atom/requirement metrics materially exceed the deterministic P38-2 baseline (requirement exact 4/18). Candidate integration is explicitly out of scope regardless of this result; a fresh semantic-atom holdout is required first.

## Executed result — No-Go

The frozen P38-2 developer set was executed once with HCX-007, Native Structured Outputs, `thinking.effort = none`, and a 6-second global request-start interval. The operational contract was clean: schema validity `18/18`, ontology validity `18/18`, unknown ontology values `0`, and provider errors `0`.

The semantic extraction feasibility gate did not pass:

| Metric | Result | Minimum |
| --- | ---: | ---: |
| Subject F1 | 0.7742 | 0.90 |
| Action F1 | 0.2581 | 0.90 |
| Field F1 | 0.8621 | 0.85 |
| Modifier F1 | 0.2500 | 0.80 |
| Multi-atom field recall | 0.7917 | diagnostic |
| Requirement exact | 0/18 | 80% |

HCX reliably selected field labels but frequently omitted the accompanying action and modifier atoms. Because the unchanged RequirementComposer treats every atom class as part of requirement identity, this produced `0/18` exact composed requirements—below both the P38-3 threshold and the deterministic P38-2 baseline of `4/18`.

P38-3 remains isolated. It must not be connected to the candidate Agent, retrieval, gate, answer generation, or citation path. The next investigation should diagnose the atom ontology/prompt representation rather than expand deterministic phrase rules or claim HCX semantic-planning generalization.
