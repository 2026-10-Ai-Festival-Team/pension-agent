# Question Bank v1

[`evaluation/question_bank_v1.jsonl`](../evaluation/question_bank_v1.jsonl)은 `eval_questions_final.csv`와 `eval_questions.json`을 공통 명세 형식으로 보존한 개발·회귀 자산이다.

## 식별자와 오염 방지

- CSV와 JSON은 모두 `EVAL-001`부터 시작하지만 같은 문항이 아니다.
- 따라서 은행 ID는 `CSV-EVAL-001`, `JSON-EVAL-001`처럼 source-set namespace를 포함한다.
- `source_item_id`는 원본 ID를 보존한다. 두 파일을 원본 ID만으로 merge해서는 안 된다.
- JSON은 이미 실제 Agent 실행에 사용됐고, CSV도 의미적으로 겹치는 문항이 있다. 둘 다 fresh holdout이나 학습 데이터가 아니다.
- P33은 이 은행과 분리된 frozen holdout으로 유지한다.

## 보존하는 계약

각 레코드는 다음 검증 자산을 담는다.

- `fixtures.planner`: 별도 검토로 채울 canonical requirement slot 자리
- `fixtures.retrieval`: JSON의 문서 ID/페이지 또는 CSV의 기대 원본 경로
- `fixtures.gate_policy`: answer, clarify, abstain 등 기대 행동
- `fixtures.generation`: gold points/서술형 gold answer와 금지 주장
- `fixtures.grounding`: 최종 주장에 필요한 원본 evidence

원본 데이터에는 canonical planner slot이 직접 제공되지 않는다. 따라서 `planner_slot_status`를 `needs_annotation`으로 둔다. gold answer를 자동으로 planner slot으로 간주하면 정답 rubric과 query understanding 명세를 혼동하게 된다.

## 생성과 검증

```bash
python scripts/build_question_bank.py
python -m pytest tests/evaluation/test_question_bank.py -q
```

생성 시 `evaluation/question_bank_v1_metadata.json`에 두 원본 파일의 SHA-256과 레코드 수를 기록한다. 이후 slot annotation이나 contrastive fixture를 추가할 때도 원본 bank를 덮어쓰지 않고 별도 versioned artifact로 만든다.
