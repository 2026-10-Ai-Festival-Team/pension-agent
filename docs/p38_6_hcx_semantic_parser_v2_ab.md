# P38-6 — HCX Structured Semantic Parser v2 A/B

## Scope

P38-6 compares the frozen P38-3 v1 output with a new isolated HCX-007 parser using P38-5 semantic contract v2. It is a developer feasibility experiment, not a generalization result.

- A: reuse `evaluation/p38_3_hcx_semantic_planner_results.json`; do not recall HCX.
- B: `subject / field / essential_qualifier / relation` Native Structured Output.
- No candidate Agent integration, retrieval, evidence, answer generation, citations, or financial policy.
- 6-second global pacing; `thinking.effort = none`.

## Metrics

- Subject, field, essential-qualifier, relation precision/recall/F1.
- Semantic requirement coverage and requirement exact after the v2 deterministic composer.
- Unsupported extra atom count.
- Schema/ontology validity and provider errors.
- Dedicated tracker for the P38-4 real-loss conditions.

## Run order

```bash
.venv/bin/python scripts/run_p38_6_hcx_semantic_parser_v2.py --execute --scope p38-2
.venv/bin/python scripts/run_p38_6_hcx_semantic_parser_v2.py --execute --scope full --reuse-subset evaluation/p38_6_v2_ab_p38_2_subset.json
```

The full run reuses the 18 subset B outputs and calls HCX only for the remaining 30 developer rows.

## Executed subset result — No-Go

P38-2's frozen 18-row subset was run once for B. A was reused from the P38-3 artifact and was not recalled. The operational contract was clean:

- schema validity: `18/18`
- ontology validity: `18/18`
- unknown ontology values: `0`
- provider errors: `0`

The semantic feasibility gate did not pass:

| Metric | V1 A | V2 B |
| --- | ---: | ---: |
| Subject F1 | 0.7742 | 0.7812 |
| Field F1 | 0.8621 | 0.9032 |
| Essential qualifier F1 | n/a | 0.4762 |
| Relation F1 | n/a | 0.2222 |
| Requirement exact | 0/18 | 3/18 |
| Semantic requirement coverage | n/a | 16/45 = 35.6% |
| Unsupported extra atoms | n/a | 19 |

V2 improves field selection and removes the action-induced `0/18` failure, but it still omits most evidence-changing qualifiers and over-specifies or mismatches relation endpoints. The real-loss tracker recovered only `isa_maturity`, `current`, and `historical`; it missed early-withdrawal, combined-limit, additional-credit, in-kind, transfer-tax-timing, and partial-versus-closure coverage.

The subset is therefore a feasibility No-Go. The 30 additional dev rows are deliberately **not called**: full characterization cannot provide useful evidence before the predeclared subset gate passes. Candidate integration remains prohibited.
