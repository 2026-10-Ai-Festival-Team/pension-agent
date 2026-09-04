# P37-A Closed Pre-HCX Failure Attribution

- Manifest SHA-256: `31cad5d15e5d93c5e9c42921d9b3398bfb18e54072b10aed9d10481b4470d6b2`
- HCX calls: **0**; candidate code was not modified.
- P37 is now a development/regression set.

## Result

- Semantic requirement coverage: **5/18**
- Evidence sufficiency: **15/18**
- Original + primary: **18/18**

## First-failure owners

- `canonical_field_miss`: **4**
- `normalization_alias_miss`: **1**
- `normalization_semantic_miss`: **7**
- `planner_multi_requirement_miss`: **1**

## Interpretation

P37 repeats the same broad weakness after P34--P36: 9 indirect action/intent phrasings and 4 product-field phrasings fail before retrieval. This is not a retrieval or HCX-generation result. Do not call HCX.

## Decision

**No-Go.** A further alias list would likely create another phrase-specific regression cycle. The next design step should reconsider the canonicalizer as a compositional subject/action/field/modifier parser before creating a new fresh holdout.
