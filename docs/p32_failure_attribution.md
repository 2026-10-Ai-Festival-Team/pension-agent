# P32-A: Failure Attribution

## Scope and evidence

P32 remains a frozen fresh holdout. This is a read-only attribution of the existing P32 execution and manual semantic labels; no Agent code, prompt, retrieval setting, or policy was changed.

- Answerable: 22
- Strict useful: 9
- Failed: 13
- Unsupported: 3, safely blocked: 3/3

The manifest declares 24 required evidence chunks for the 22 answerable questions. All **24/24** are present in `data/parsed/chunks.jsonl`, and each corresponding source filename exists under `data/raw`. Therefore none of the 13 failures is primarily `corpus_missing`.

Provider, JSON/schema, and citation validation were also all successful in the executed run. They are not primary causes here.

## Primary-cause distribution

| Owner | Failed questions | Count |
|---|---|---:|
| Planner | P32-009, P32-015, P32-017 | 3 |
| Matcher | P32-014 | 1 |
| Requirement coverage after evidence delivery | P32-002, P32-010, P32-012 | 3 |
| Product-field interpretation | P32-013 | 1 |
| HCX evidence interpretation | P32-006 | 1 |
| Financial-policy false rejection | P32-016, P32-018, P32-025 | 3 |
| Financial-policy unsafe pass | P32-019 | 1 |
| Corpus or retrieval primary cause | — | 0 |

Deterministic orchestration/policy owns **8/13** failures before generation (planner, matcher, or policy), and the downstream requirement/field boundary owns another **4/13**. Only P32-006 is a pure `generation_misread`. This does **not** justify tuning at this point.

## Case-level forensic findings

| ID | Primary cause | Evidence-path finding | Why it failed |
|---|---|---|---|
| P32-002 | `requirement_omission` | An equivalent retrieved chunk contains both 1,800만원 납입 and 900만원 세액공제 limits. | Simple route created no slots; answer denied full deduction but omitted the limit distinction. |
| P32-006 | `generation_misread` | The selected DB/DC comparison table supports all four required facts. | HCX incorrectly treated DC benefit calculation as average-wage based. |
| P32-009 | `planner_miss` | Selected DB/DC comparison evidence includes conversion and DC contribution information. | Plan added unasked 규약·동의 and omitted the required DC contribution criterion; the gate block is consequential. |
| P32-010 | `requirement_omission` | Housing-purchase withdrawal and IRP withdrawal-rule evidence entered context. | Simple path supplied no checklist, producing only “different” rather than the required comparison. |
| P32-012 | `requirement_omission` | Selected same-document cost table covers both field types. | Answer states they differ but does not explain annual fee and three-year example. |
| P32-013 | `field_confusion` | Exact A1 cost table was selected. | It substituted sales-fee ceiling `0.8%` for total cost `0.6644%`, and two-year `218천원` for three-year `292천원`. |
| P32-014 | `matcher_miss` | Selected primary table explicitly supports 4등급, 실적배당, no deposit protection, and potential loss. | Product-bound loss matcher did not accept the actual table wording, so generation was blocked. |
| P32-015 | `planner_miss` | Risk-grade evidence arrived; the plan did not ask for investment strategy. | No strategy retrieval/query was generated, so the 90%+ equity allocation requirement was omitted. |
| P32-016 | `policy_false_reject` | No factual document evidence is needed for the expected action. | A condition-poor recommendation needs first-turn clarification, not generic unsupported blocking. |
| P32-017 | `planner_miss` | Route was compound, but its plan was empty. | The gate blocked instead of producing a non-single-product comparison based on the stated horizon/risk tolerance. |
| P32-018 | `policy_false_reject` | No product fact is required to identify the stated preference conflict. | Policy returned a generic block instead of explaining loss avoidance versus equity-fund risk. |
| P32-019 | `policy_unsafe_pass` | Simple evidence-present path invoked HCX. | It made an individual tax-minimization recommendation without required personal conditions. |
| P32-025 | `policy_false_reject` | Original/corpus evidence supports the past-performance premise correction. | Future-looking wording was mistaken for unsupported recommendation and blocked before evidence-grounded correction. |

## Successful paths

P32-001, P32-003, P32-004, P32-005, P32-007, P32-008, P32-011, P32-023, and P32-024 completed the full original-evidence → retrieval → gate → HCX → policy path and were manually labeled strict useful.

## Decision

**P32 remains No-Go.** Do not use it to claim P31 v2 generalization, and do not tune to this set then score the same set again.

The next valid sequence is:

1. Design generalized fixes for the planner/matcher/policy causes above.
2. Re-run existing regression suites without redefining P32 as a success metric.
3. Create a new, unused P33 fresh holdout before claiming generalized improvement.
