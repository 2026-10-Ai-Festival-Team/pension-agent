# 평가셋 작성 규칙

`eval_questions.json`과 CSV는 대회 원본 문서를 직접 확인한 뒤에만 작성합니다. production 코드는 이 디렉터리를 읽지 않습니다.

필수 JSON 필드는 `id`, `category`, `subcategory`, `difficulty`, `question_type`, `question`, `expected_behavior`, `gold_answer_points`, `required_evidence`, `must_not_include`입니다. `required_evidence` 항목은 실제 `document_id`와 `page`를 포함해야 합니다. `clarify` 문항은 `required_clarifications`도 포함합니다.

목표 분포는 30문항(제도 5, 세제 5, 종합 5, 절차 3, 상품 5, 조건부 추천 5, robustness 2), 난이도 low 8 / medium 14 / high 8입니다.
