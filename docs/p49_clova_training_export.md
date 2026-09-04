# P49 CLOVA Training Export Contract

P49 tunes **Generator behaviour**, not pension knowledge.  Every training row
must reproduce the runtime information boundary:

```text
question + canonical requirements + selected direct evidence
→ evidence-faithful answer
```

The canonical contract is
`evaluation/fine_tuning/p49_clova_training_export_contract_v1.json`.

## Why direct evidence is part of `Text`

A question-only row can teach a model to associate a pension question with a
memorised answer.  The export instead places only the selected, direct corpus
evidence alongside the question and requirement.  The Completion teaches the
model to read that evidence faithfully, cover all requested fields, and avoid
nearby but unrequested fields.

```text
[질문]
DB는 내가 직접 굴리는 거지?

[요구사항]
DB.operation_party

[근거]
DB형 퇴직연금의 적립금 운용 주체는 회사이다.
```

The corresponding completion may correct the user's premise, but it must not
add a factual statement absent from the supplied evidence.

## Export boundary

The future export adapter converts a frozen canonical record into one CLOVA
instruction row:

```json
{
  "C_ID": 0,
  "T_ID": 0,
  "System_Prompt": "제공된 근거만 사용해 질문에 답하세요.",
  "Text": "[질문] ...\\n\\n[요구사항] ...\\n\\n[근거] ...",
  "Completion": "[답변] ...\\n[근거] ...\\n[유의사항] ..."
}
```

Internal audit values, reviewers, hashes, source-seed IDs, and taxonomy codes
stay in a separate manifest.  They are not generator input or completion text.
The adapter must fail an oversize row rather than silently truncating its
evidence.

## Outcomes

- `supported_answer`: answer all directly supported requested facts.
- `clarification_required`: ask for the smallest missing user condition.
- `bounded_answer`: state what the evidence cannot establish, then answer only
  the supported part.

All contrastive examples still have correct completions.  They contrast a
nearby field in the question/evidence relationship; they never train a wrong
answer.

## Gates and sequence

No export adapter, Object Storage upload, tuning API call, or tuned generator
activation occurs until P49-2H records have passed evidence-first QA and the
training candidate plus P50 holdout are frozen.

After that freeze, NCP-2A separates the HCX-007 structured selector client
from the configurable answer-generator client.  Only then may a future NCP-2B
adapter export rows and upload the immutable artifacts.  A/B/C evaluation keeps
the selector, resolver, retrieval, evidence gate, and citation validator fixed:

```text
A: HCX-007 selector + HCX-007 generator
B: HCX-007 selector + untuned HCX-005 generator
C: HCX-007 selector + tuned HCX-005 generator
```
