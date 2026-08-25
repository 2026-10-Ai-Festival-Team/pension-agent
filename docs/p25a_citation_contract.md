# P25-A: HCX Citation Contract 반복 검증

R-002와 R-006은 각각 한 번 결정한 동일 selected evidence·context 순서를 유지한 채 HCX-007에 3회씩 전달했다. Router, retrieval, gate, FinancialAnswerPolicy, validator는 변경하지 않았다.

## Citation 계약

- JSON/schema 통과: 6/6
- full `chunk_id` 반환 및 validator 통과: 6/6
- R-002: 3/3
- R-006: 3/3

## Semantic 수동 검토

- 직접적·충분한 답변: 4/6
- 부분 충족: 2/6
- R-006의 2회는 full chunk_id를 정확히 인용했지만, 질문의 DB→DC 전환 조건보다 일반적인 퇴직연금규약 변경 사유를 중심으로 답했다.

## 판정

**Citation contract: Pass.** full `chunk_id` exact-copy, JSON/schema, strict validator를 6/6 통과했다. source_id 자동 보정이나 validator 완화는 사용하지 않았다.

**Generation requirement coverage: Backlog.** R-006의 부분 충족은 citation ID 문제가 아니라, 선택된 근거를 질문 요구에 맞게 우선순위화하는 생성 품질 이슈다. P25-B provider stability와 분리해 후속 E2E semantic 평가에서 다룬다.

원문 HCX 응답과 answer 본문은 `data/diagnostics`에만 저장한다. 이 보고서와 semantic label에는 hash·판정·사유만 포함한다.
