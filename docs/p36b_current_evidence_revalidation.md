# P36-B Current Evidence Revalidation

- HCX 호출: **0**. P36-B current preparation artifact만 검토했다.
- Frozen P36 manifest SHA-256: `6ee433b5fbe323be49889c2c13690d5fb96874a5069ac5e7b40ce6a5621913a8`
- semantic-equivalent 판정은 현재 selected chunk IDs와 결속되며, evidence set이 바뀌면 자동으로 무효다.

## Result

- Semantic requirement coverage: **18/18**
- Evidence sufficiency: **18/18**
- Original + primary: **18/18**
- Exact gold: **13/18**
- Semantic equivalent: **5/18**
- Exact + equivalent: **18/18**
- Partial / wrong-scope / drift: **0 / 0 / 0**

## Decision

P36-B is a development-regression **Go** only when all figures above are 18/18 and partial/wrong-scope/drift are zero. P36 remains a development set; fresh generalization must be demonstrated by a newly frozen P37 holdout.
