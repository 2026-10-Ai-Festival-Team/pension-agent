# P39-1 — Direct Requirement Selector A/B/C (Development Feasibility)

## Scope

P38-2의 18개 개발 문항에서 Closed factual requirement를 같은 P39
canonical vocabulary로 비교했다. 이 실험은 candidate Agent, retrieval,
matcher, citation, financial policy에 연결하지 않았다.

| Method | Role |
| --- | --- |
| A | Existing production `RequirementBuilder` projected into the P39 vocabulary |
| B | Frozen P38-7B HCX semantic-atom parser output projected into the P39 vocabulary |
| C | New HCX-007 Native Structured Output direct multi-label requirement selector |

C는 model이 `DIRECT_REQUIREMENTS` enum 안에서만 선택하도록 했으며, 상품
코드는 질문에서 deterministic하게 추출했다. C는 product identity나 새로운
requirement 이름을 생성하지 않는다.

## Frozen input

- Manual direct-selector gold: `question_bank/development/p39_1_direct_requirement_selector_gold.jsonl`
- Questions: 18 P38-2 development rows
- Manifest SHA-256: `0bcf5771a8399b5120e3abcd2b9b11f66c242b5211db3335f2da9993f366c499`
- C model/runtime: HCX-007, Native Structured Outputs, thinking none, 6-second hard pacing

## Result

| Method | Precision | Recall | Exact | Multi-requirement recall | Extra | Missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A. Existing production planner | 92.3% | 28.6% | 3/18 (16.7%) | 30.0% | 1 | 30 |
| B. Frozen P38 atom parser | 93.5% | 69.1% | 11/18 (61.1%) | 67.5% | 2 | 13 |
| C. P39 direct selector | **97.6%** | **95.2%** | **16/18 (88.9%)** | **95.0%** | **1** | **2** |

C runtime contract:

- Schema validity: 18/18
- Ontology validity: 18/18
- Unknown enum value: 0
- Provider error: 0
- Deterministic product-code resolution: 18/18
- Live HCX calls: 18

## Pre-holdout gold-contract review

`P38-2-009` was reviewed before creating a fresh holdout. Its wording asks
where DB·DC and IRP users apply; it does not ask to define an in-kind transfer.
The definition is therefore now an `optional_supporting_requirement`, while
the two application routes remain required. This is a gold-contract correction,
not a selector change and not a new HCX call. The original live artifact is
retained; the revised offline score is in
`evaluation/p39_1_direct_requirement_selector_ab_contract_review.json`.

## Remaining C mismatch after contract review

| Question | Frozen gold vs C | Interpretation for next diagnostic |
| --- | --- | --- |
| P38-2-016 | Missing `DC.operation_party`; extra `DB.operation_party` | Actual scope-resolution error: “그 제도” refers to DC after the employer-contribution distinction. This is a selector semantic error. |

## Decision

**P39-1 development feasibility: Go.** C clears the agreed development
thresholds for recall, precision, exact match, multi-requirement recall,
schema validity, unknown enum values, and provider stability.

This is not a generalization result. The 18 questions and their manual gold
are development data. Do not connect C to the browser/candidate path yet.
First freeze the contract after the two mismatch attributions, then run a
fresh direct-selector holdout before shadow integration.

Raw metrics and per-question outputs: `evaluation/p39_1_direct_requirement_selector_ab.json`.
