# P39-3 — Fresh Direct-Selector Holdout

## Protocol

P39-2 was invalidated by an execution-harness save failure after its 18 live
calls. It was not rerun. P39-3 is a new 18-question Closed factual holdout,
with normalized duplicate checks against existing question-bank and holdout
assets before HCX execution.

- Manifest: `question_bank/holdouts/p39_3_direct_requirement_selector_holdout.jsonl`
- Manifest SHA-256: `db7fece6924f4b7183fd227e57b453b29ae06b5f65cd2b970426b94ffff1b679`
- Model: HCX-007 Native Structured Outputs; thinking none; 6-second pacing
- Scope: isolated selector only; candidate Agent, retrieval, answer generation,
  citation, and policy were not used or changed.

## Operational contract

| Metric | Result |
| --- | ---: |
| Schema valid | 18/18 |
| Ontology valid | 18/18 |
| Unknown enum value | 0 |
| Provider errors | 0 |
| Raw selection hashes | 18/18 persisted |

## Requirement metrics

| Metric | Result | P39-2 target |
| --- | ---: | ---: |
| Requirement precision | 97.1% | ≥90% |
| Requirement recall | 94.4% | ≥90% |
| Requirement exact | 16/18 = 88.9% | ≥80% |
| Multi-requirement recall | 93.9% | ≥90% |
| Unsupported extra requirements | 1 | very low |
| False missing requirements | 2 | — |

## Scope-critical failures

| ID | Failure | Owner |
| --- | --- | --- |
| P39-3-001 | Selected DB/DC benefit-determination requirements but omitted `DC.operation_party` | Direct selector multi-requirement scope omission |
| P39-3-003 | Selected `DC.employer_contribution` but omitted `DC.operation_party` | Direct selector multi-requirement scope omission |
| P39-3-018 | Requirement field was correct, but deterministic product resolver returned both named products although “뒤에 적은 상품” identifies only the second | Deterministic product reference-resolution gap, outside the HCX selector |

The first two are factual scope losses. The third is a product-subject binding
failure. All three can produce a wrong downstream evidence bundle even though
aggregate requirement precision/recall is high.

## Decision

**P39-3: No-Go for shadow integration.**

The direct selector is a strong candidate on requirement-label extraction, but
it does not yet meet the agreed scope-error criterion. Do not connect it to
the browser or production candidate path. Preserve P39-3 as a development
regression set and perform failure attribution before changing selector or
deterministic product reference resolution.

Raw results and hashes: `evaluation/p39_3_fresh_direct_requirement_selector_holdout.json`.
