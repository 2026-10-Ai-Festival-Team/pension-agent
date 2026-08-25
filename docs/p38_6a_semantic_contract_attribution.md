# P38-6A — Semantic Contract vs Real Semantic Miss Attribution

## Frozen boundary

- HCX calls: `0`
- parser/prompt/ontology/composer changes: `0`
- candidate/retrieval/matcher/policy changes: `0`
- gold changes: `0`
- P38-6 source-result changes: `0`

This diagnosis reads only the frozen P38-6 subset output and frozen v2 gold.

## Required reading of the result

The official P38-6 score is unchanged. The diagnostic does **not** relax the score; it assigns one owner to every frozen component mismatch and separately labels each question as fully preserved, partially preserved, or meaning lost.

See `evaluation/p38_6a_semantic_contract_attribution.json` for all 18 question-level gold/prediction plans, requirements, mismatch owners, and evidence effects.

## Attribution result

The frozen subset contains 45 component-level mismatches:

| Owner | Count |
| --- | ---: |
| `contract_equivalent` | 2 |
| `contract_granularity_mismatch` | 1 |
| `relation_representation_mismatch` | 9 |
| `real_semantic_miss` | 17 |
| `unsupported_extra` | 16 |
| `ontology_ambiguity` | 0 |
| `gold_contract_issue` | 0 |

All 19 frozen “unsupported extra” outputs are accounted for: 16 are genuinely unsupported, two are endpoint-bearing comparison-relation representations, and one places the transfer-source event in `subjects` rather than the relation.

Question-level diagnostic preservation is `4/18` fully preserved, `3/18` partially preserved, and `11/18` meaning lost. Thus relation-contract mismatches explain some exact-match failures, but cannot explain away the low 35.6% frozen semantic-requirement coverage.

The core real losses are account/system scope substitutions, early-withdrawal and combined-limit qualifiers, ISA additional credit and destination scope, in-kind transfer, transfer-specific tax timing, risk-grade changeability, and partial-withdrawal/account-closure tax fields.

## Decision rule

The architecture recommendation is attribution only. P38-6A implements no recommendation.
