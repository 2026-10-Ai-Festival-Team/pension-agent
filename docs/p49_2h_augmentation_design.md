# P49-2H Domain-Grounded Augmentation Design

P49 Gold Seed v2는 field 정확성·누락 방지·evidence fidelity의 기준점으로
동결되어 있다. P49-2H는 이를 수정하지 않고 실제 사용자 표현과 outcome
분포를 확장하는 단계다.

## Frozen axes

`evaluation/fine_tuning/p49_2h_taxonomy_v1.json`에 다음 독립 축을 정의한다.

- Question type: `Q01`~`Q20`
- Factual domain: `D01`~`D30`
- Outcome: `O01`~`O03`

`correction`과 `stance`는 outcome이 아닌 modifier다. 따라서 예를 들어
DB 운용주체를 잘못 이해한 확인형 질문은 다음처럼 기록한다.

```json
{
  "question_type": "Q08",
  "factual_domain": "D01",
  "outcome": "O01",
  "modifiers": {
    "correction": true,
    "stance": "contradict",
    "evidence_status": "full"
  }
}
```

## Scope boundary

P49-2H core는 single-active-subject factual lane이다. 명시적인 양자 비교는
`deferred_comparison`으로 분리한다. 현재 runtime contract에서
`non_unique_active_subject`를 fail-closed 처리하는 기능 경계를 데이터로
숨기지 않는다.

Domain taxonomy는 coverage 계획표이며 모든 Domain이 즉시 학습 export 대상은
아니다. `support_status=\"schema_mapping_pending\"` Domain은 direct requirement와
direct-evidence binding을 먼저 정의하기 전까지 augmentation 후보·training export에서
제외한다. 상품 식별(D29)은 generator가 고르는 factual requirement가 아니라
deterministic product resolver의 provenance 검증 항목이다.

## Record construction order

```text
original corpus evidence
→ factual domain / selected requirement
→ user question type
→ outcome + modifiers
→ direct-evidence gold completion
→ automated QA
→ human review
```

질문 표현을 먼저 만들고 그에 맞는 사실을 추정하지 않는다. 모든 factual
claim은 input `direct_evidence`에서 직접 확인되어야 한다.

## Next input gate

사용자가 8~12개 질문 유형에 대해 실제 질문 3~5개씩 작성한 human seed를
제공한다. 그 전에는 augmentation record·training export·tuning을 만들지
않는다.

## Generator training boundary

P49-2H record가 최종적으로 학습 후보가 되더라도, 질문만 CLOVA 학습 입력에
넣지 않는다. `question + selected requirement + selected direct evidence`를
입력으로 사용해 Generator가 해당 evidence를 정확하고 완전하게 읽도록 한다.
세부 계약은 [P49 CLOVA Training Export](p49_clova_training_export.md)를
따른다. 이 단계에서 HCX-005 tuning, Object Storage upload, 또는 runtime
generator 교체를 시작하지 않는다.
