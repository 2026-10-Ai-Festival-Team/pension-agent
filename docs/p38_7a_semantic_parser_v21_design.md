# P38-7A — Semantic Parser v2.1 Contract Design

## Scope and frozen boundary

This phase designs the v2.1 contract from the frozen P38-6A attribution. It
does **not** call HCX or change the candidate Agent, retrieval, policy, v2
parser, prompt, ontology, composer, gold, or P38-6 result.

- HCX calls: `0`
- Candidate integration: `0`
- Existing v2 implementation changes: `0`
- Frozen P38-6A mismatches accounted for: `45/45`

The machine-readable design audit is
`evaluation/p38_7a_semantic_contract_v21_design.json`.

## v2.1 responsibility boundary

```text
Raw question
  -> deterministic lexical entity normalization
  -> HCX semantic interpretation
       subjects + fields + essential qualifiers + directional transfer only
  -> deterministic validator
       canonical scope / enum / directional completeness
  -> deterministic derivation and composition
       generic comparison + requirements
```

HCX must never write an answer, retrieve evidence, select a citation, invent a
factual value, or emit a generic comparison relation.

## Contract decisions

### Canonical subject scope

`account:pension` and `system:retirement_pension` are not aliases. The former
is an account-specific tax or withdrawal scope; the latter is the broader
retirement-pension system. A scope substitute is rejected, not silently made
equivalent.

### Comparison versus transfer

Generic comparison is derived deterministically only when both conditions hold:

1. the question has comparison intent; and
2. the validated plan contains at least two subjects.

The HCX schema therefore has no `comparison` relation. It avoids endpoint-free
gold versus endpoint-bearing HCX representations of the same comparison.

Transfer remains an HCX relation because direction changes the evidence:
`ISA -> pension account` is not interchangeable with an undirected pair. Its
source and destination must be complete canonical subjects and must not be
duplicated as loose event subjects.

### Essential distinctions are still strict

The following are not relaxed: `before_retirement`, `combined_limit`,
`additional_credit`, `in_kind`, transfer-specific tax timing,
`change_possibility`, and the separate partial-withdrawal versus account-closure
fields and tax treatment. Their loss changes the factual evidence required.

### Precision-first parser behavior

The v2.1 prompt must say, in substance:

> Output only factual distinctions explicitly or semantically requested by the
> user. Do not add related scopes, fields, qualifiers, products, events, or
> future-change concepts. If a distinction is not asked, omit it.

This targets the 16 diagnostic unsupported-extra mismatches; it is not a
scoring relaxation.

## Frozen mismatch disposition

| Frozen attribution | Count | v2.1 handling |
| --- | ---: | --- |
| Contract equivalent | 2 | Do not require a generic HCX comparison relation. |
| Contract granularity mismatch | 1 | Keep transfer source context in the directional relation, not in `subjects`. |
| Relation representation mismatch | 9 | Derive generic comparison deterministically after subject validation. |
| Real semantic miss | 17 | Preserve the missing scope, factual field, qualifier, or transfer direction as a strict v2.1 target. |
| Unsupported extra | 16 | Apply precision-first prompt and reject/measure additions as extras. |

The per-question design mapping records retained and forbidden distinctions.

## P38-7B gate

Only after this design is frozen, run the isolated v2.1 parser on the existing
P38-2 development subset. Compare it with frozen v2 without candidate
integration. The experiment must show a material reduction in both meaning loss
and unsupported extras while retaining directional transfer endpoints. A fresh
semantic holdout remains mandatory before any candidate integration.
