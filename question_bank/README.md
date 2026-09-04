# 질문은행

이 폴더는 질문 데이터의 **용도와 상태를 한곳에서 찾기 위한 카탈로그**입니다. 기존 `evaluation/` 원본은 테스트·스크립트가 참조하므로 이동하지 않았습니다. 같은 질문을 복사해 두지 않고, 아래 `catalog.json`의 경로를 canonical source로 사용합니다.

## 구분

| 구분 | 용도 | 현재 자료 |
| --- | --- | --- |
| `closed/` | 문서에 객관적 정답이 있는 제도·세제·절차·상품 factual QA 개발 회귀 | Closed Core 46문항 |
| `development/` | 이미 결과를 확인해 코드 개선에 사용 가능한 개발·회귀셋 | P32, P33, P34, P35 |
| `holdouts/` | 코드를 동결한 뒤에만 실행할 새 holdout | 현재 없음 — 다음은 P36으로 새로 동결 |

## 운영 규칙

- `holdouts/`에 새 manifest를 만든 뒤에는 **HCX 실행 전까지 Agent 코드를 바꾸지 않습니다.**
- 결과를 분석하거나 수정에 사용한 holdout은 즉시 `development/`로 상태를 바꿉니다.
- 추천·개인화·unsupported는 Closed factual benchmark와 분리합니다.
- 각 문항에는 `question`, `answerability`, `required_requirements`, `acceptable_equivalent_evidence`, `must_not_include`를 유지합니다.
- gold는 한 개의 문장보다 requirement와 원본 evidence를 기준으로 판정합니다.

실제 파일 경로와 현재 상태는 [catalog.json](catalog.json)에 있습니다.

`eval_questions_final.csv`와 `eval_questions.json`도 30문항 competition-style 평가셋으로 카탈로그에 포함했습니다. 이미 실행·분석에 사용했으므로 fresh holdout이 아닌 개발 회귀셋으로 분류합니다.

`normal_questions.jsonl`과 `robustness_questions.jsonl`은 원본을 이동하지 않고 카탈로그 참조로 등록했습니다. 그중 Closed factual 18문항은 `development/closed_factual_reviewed_v1.jsonl`에서 **strict required facts / optional supporting facts / forbidden claims**로 다시 분리합니다. N-014의 추가 서류·예외 정보는 원본 evidence 연결 전까지 strict 판정에 쓰지 않습니다.
