# P38-7B — Isolated HCX Semantic Parser v2.1 A/B

## Scope

- Development-only P38-2 subset: `18` questions
- A: frozen P38-6 v2 artifact
- B: new HCX-007 Native Structured Outputs v2.1 parser
- Pacing: `6` seconds, sequential
- Candidate Agent / retrieval / matcher / citation / policy: unchanged and unused
- Answer generation: unused

This is a feasibility comparison, not a generalization or production result.

## Runtime contract

| Metric | Result |
| --- | ---: |
| Schema valid | 18/18 |
| Ontology valid | 18/18 |
| Unknown ontology values | 0 |
| Provider errors | 0 |
| Live HCX calls | 18 |

## A/B result

| Metric | Frozen v2 | v2.1 | Readout |
| --- | ---: | ---: | --- |
| Subject F1 | 0.7812 | 0.7667 | Regressed slightly |
| Field F1 | 0.9032 | 0.8710 | Regressed |
| Essential qualifier F1 | 0.4762 | 0.3000 | Regressed |
| Directional-transfer F1 | n/a (generic relation mixed in) | 0.5000 | Below gate; only one of two directions preserved |
| Semantic requirement coverage | 0.3556 | 0.4884 | Improved, but far below 80–85% gate |
| Requirement exact | 3/18 (16.7%) | 6/18 (33.3%) | Improved, but far below 75–80% gate |
| Raw unsupported extras | 19 | 16 | Apparent reduction is largely removal of generic-comparison representation; P38-6A already classified 16 as genuine extras |
| v2.1 real semantic misses | n/a | 22 | Still high |

## Essential-condition tracker

Recovered: `isa_maturity`, `current`.

Not recovered: `before_retirement`, `combined_limit`, `not_tax_exempt`,
`additional_credit`, `in_kind`, `change_possibility`, `historical`,
`tax_timing_on_transfer`, and partial-versus-closure tax distinction.

The two directional transfer cases split: the retirement-benefit-to-IRP direction
was preserved, but ISA-to-pension-account was emitted with the over-broad
retirement-pension-system destination.

## Decision: No-Go

v2.1 removed the avoidable generic-comparison output contract, so requirement
coverage and exactness rose. It did **not** meet its actual objective: real
semantic omissions and genuinely unsupported extras remain high, while field
and essential-qualifier accuracy fell. Therefore:

- do not integrate v2.1 into the candidate Agent;
- do not run a fresh semantic holdout yet;
- do not interpret 16 versus 19 raw extras as a real precision win without the
  P38-6A attribution distinction.

The next work should be failure attribution of the v2.1 output itself, focused
on account/system scope substitutions, essential qualifier recall, and
precision errors. It should not be another blind prompt expansion.
