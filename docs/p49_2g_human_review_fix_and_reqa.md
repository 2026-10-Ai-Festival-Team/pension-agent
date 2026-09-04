# P49-2G Human Review Recommended Fixes + Re-QA

## Status

**Automatic QA Go / Human approval Pending.** v1 drafts remain unchanged for audit; this report and v2 files are review-preparation artifacts, not frozen training data.

- Modified: 14/14
- Unchanged regression records: 24/24
- Automatic QA: 38/38
- Human approved: 0/38
- Human pending: 38/38
- Tuning API calls: 0
- NCP resource changes: 0

## Record changes

| Record | Before → after completion hash | Reason | QA |
| --- | --- | --- | ---: |
| `contrastive_draft-p45-010` | `a127067bc4f4` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |
| `contrastive_draft-p45-018` | `e23d95731e6b` → `41a2d314e7f5` | DB 급여 산정의 두 요소와 산식 관계를 직접 근거 표현으로 명확화 | PASS |
| `contrastive_draft-p46-013` | `995436f02b31` → `b00b7b743b53` | 명시적으로 주어진 상품코드를 후자라는 불필요한 참조로 다시 해석하지 않도록 수정 | PASS |
| `contrastive_draft-p46-016` | `3adeca903c7d` → `897f80420386` | DB 급여 산정의 두 요소와 산식 관계를 직접 근거 표현으로 명확화 | PASS |
| `contrastive_draft-p47-008` | `7b76685c062a` → `ae6fe5f68014` | 위험등급 변경 가능성의 문체를 자연스럽고 직접적인 표현으로 수정 | PASS |
| `contrastive_draft-p47-010` | `7ae7a08c70d3` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |
| `contrastive_draft-p48-010` | `0521c53ae05b` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |
| `contrastive_draft-p48-014` | `11d99201f21a` → `b285279ec346` | negative contrast에서 제외된 판매수수료 field를 답변에 다시 쓰지 않도록 수정 | PASS |
| `positive_draft-p45-010` | `a127067bc4f4` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |
| `positive_draft-p45-018` | `e23d95731e6b` → `41a2d314e7f5` | DB 급여 산정의 두 요소와 산식 관계를 직접 근거 표현으로 명확화 | PASS |
| `positive_draft-p46-016` | `3adeca903c7d` → `897f80420386` | DB 급여 산정의 두 요소와 산식 관계를 직접 근거 표현으로 명확화 | PASS |
| `positive_draft-p47-008` | `7b76685c062a` → `ae6fe5f68014` | 위험등급 변경 가능성의 문체를 자연스럽고 직접적인 표현으로 수정 | PASS |
| `positive_draft-p47-010` | `7ae7a08c70d3` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |
| `positive_draft-p48-010` | `0521c53ae05b` → `6455d800cc43` | product.total_fee에서 합성총보수·비용을 자동 대체 field로 병기하지 않도록 정밀화 | PASS |

## Remaining human review

Each v2 record remains `pending`. A human reviewer must still confirm naturalness, financial meaning, direct-evidence fidelity, field precision, and the contrastive target before any `approved` state or freeze.

## Next step after approval

Only after the final ledger contains the human decisions should approved records be promoted into a canonical Gold Seed v1 dataset and its immutable manifest/hash be created.
