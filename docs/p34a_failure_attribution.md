# P34-A Pre-HCX Failure Attribution

## Scope

- Frozen P34 manifest SHA-256: `9af34d000cd83b22abd3de3fa44fd4c4c2db5cb589ab5dea6c37245b2fd7e5ba`
- HCX 호출 없음. 이 문서는 Agent 수정 전 attribution만 기록한다.
- P34는 이 분석 후 development/regression set이며 generalisation claim에 재사용하지 않는다.

## Planner / preparation owners

- `planner_intent_miss`: **4**
- `planner_schema_variant`: **1**
- `planner_slot_miss`: **2**

## Current source relevance

- Exact gold: **10**
- Semantic equivalent: **4**
- Partial: **3**
- Wrong scope: **1**
- Stale adjudications: **0**

## Decision

P34 pre-HCX remains **No-Go**. The primary failure is Planner generalisation; source relevance additionally contains three partial selections and one wrong-scope selection. Do not call HCX. Any later Agent change must be evaluated first on the development regressions, then on a new P35 holdout.
