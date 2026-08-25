# P34-B Current Evidence Revalidation

## Scope

- HCX 호출 없음; 현재 P34-B pre-HCX selected chunks만 재판정했다.
- same-document 여부가 아니라 subject + field + value/condition + scope로 판정했다.
- required current chunk가 바뀌면 해당 semantic-equivalent 판정은 자동으로 무효다.

## Result

- Exact gold: **10/18**
- Current semantic equivalent: **8/18**
- Exact or equivalent: **18/18**
- Partial: **0**
- Wrong scope: **0**
- Evidence-set drift requiring revalidation: **0**

## Decision

Source relevance passes only for this frozen P34-B evidence selection. No partial or wrong-scope chunk is promoted to a factual requirement.
