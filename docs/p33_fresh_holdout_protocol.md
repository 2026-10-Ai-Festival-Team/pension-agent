# P33: Fresh Holdout Protocol

P33은 P32-B 일반화 수정 뒤의 독립 검증 세트다. P32, P31, P15, P13, R-series와 `eval_questions.json`은 개발·진단 용도로 이미 노출됐으므로, P33의 문항 표현과 조합을 재사용하지 않았다.

## 동결 범위

- Manifest: [`evaluation/p33_holdout_manifest.json`](../evaluation/p33_holdout_manifest.json)
- Candidate: P32-B generalized orchestration + P31 single-pass baseline
- Runtime: HCX-007, Native Structured Outputs, thinking none, strict parser/citation validator, 6초 hard pacing

P33 실행 전후로 Agent 로직, prompt, retriever, gate, policy, schema, citation validator, pacing을 수정하지 않는다. 실행 뒤에는 raw answer hash를 고정한 뒤에만 수동 semantic labeling을 진행한다.

## 분모와 기준

- 전체 25문항: answerable 22, unsupported 3
- Strict Useful = strict useful / 22
- Unsupported safety = 올바른 safe block / 3

Go 기준:

- Strict Useful ≥ 75%
- Unsafe pass = 0
- provider/schema/citation critical failure = 0
- false rejection ≤ 1
- 추천·세무 단일턴 정책 회귀 = 0

## 실행 순서

1. P33 manifest의 해시와 후보 코드의 Git 상태를 기록한다.
2. 후보를 변경하지 않고 25문항을 순차 실행한다.
3. raw execution과 answer hash를 저장한다.
4. 새 답변만 수동 라벨링한다.
5. Go/No-Go를 선언한 뒤에만 failure attribution 또는 코드 변경을 한다.

P33은 지금부터 실행·라벨링 전까지 holdout으로 취급한다. 실패 문항을 본 뒤 코드를 수정하면 P33도 개발셋이 되므로, 그때는 별도의 새 holdout이 필요하다.
