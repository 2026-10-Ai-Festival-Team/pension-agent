# P49-2 Dataset QA Review Bundle

이 파일은 학습 업로드물이 아닌 human-approval 검토용 초안입니다. 모든 record는 자동 QA를 통과했지만 승인 전에는 export/freeze 대상이 아닙니다.

- positive drafts: 19
- contrastive drafts: 19
- automatic QA: 38/38
- human approval: 0/38
- tuning API calls: 0

## Approval rule

각 completion이 질문의 모든 required fact를 포함하고, 직접 근거 밖 주장을 하지 않으며, 인접 field를 답으로 대체하지 않았을 때만 `approved`로 바꿉니다.

## positive_draft-p45-010

- Source seed: `seed-p45-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047의 지급비율 표에서 연간 총보수·비용률을 확인하려면 어떤 항목을 봐야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 구분해 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p45-011

- Source seed: `seed-p45-011`
- Requirements: `product.period_cost`
- Evidence: `9175b4d6847de4c3-table-9ed35d020b3b`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111에 1,000만원을 투자한다고 할 때 3년 보유 비용 예시는 어느 표에서 확인하나요?

**Completion**

```text
[답변] 1,000만원 투자 시 투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-9ed35d020b3b
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p45-013

- Source seed: `seed-p45-013`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR510902511M 다음에 KR5111420047을 적었습니다. 두 번째 상품의 연간 총보수·비용률은 문서의 어느 항목으로 확인해야 하나요?

**Completion**

```text
[답변] 두 번째 상품은 KR5111420047입니다. 지급비율(연간, %)의 총보수·비용 항목을 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p45-015

- Source seed: `seed-p45-015`
- Requirements: `product.period_cost`
- Evidence: `1294013a2a74e0a4-table-0689dcaed960`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5110501016의 1,000만원 투자 기준 기간별 비용 예시는 몇 년 단위 열로 제시되어 있나요?

**Completion**

```text
[답변] 기간별 비용 예시는 1년·2년·3년·5년·10년 보유 기간별 비용 예시 열로 제시됩니다.
[근거] 1294013a2a74e0a4-table-0689dcaed960
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p45-016

- Source seed: `seed-p45-016`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027의 연간 총보수·비용률을 볼 때 판매수수료와 구분해서 확인해야 할 표의 항목은 무엇인가요?

**Completion**

```text
[답변] 지급비율(연간, %) 표에서 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해서 읽어야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p45-018

- Source seed: `seed-p45-018`
- Requirements: `DB.operation_party, DB.benefit_determination`
- Evidence: `4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
DB형 적립금은 누가 운용하며, 퇴직급여 산정에는 어떤 기준이 함께 쓰이나요?

**Completion**

```text
[답변] DB형은 회사가 적립금을 운용합니다. 퇴직급여 산정에는 퇴직 전 평균임금 30일분과 계속근로기간으로 퇴직급여 산정하는 기준이 함께 쓰입니다.
[근거] 4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p46-009

- Source seed: `seed-p46-009`
- Requirements: `product.period_cost`
- Evidence: `0a1c8fece530be69-table-f26fac86b527`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420016을 1,000만원 매수했다고 가정한 비용 예시는 1년부터 어떤 보유기간 열로 나뉘어 있나요?

**Completion**

```text
[답변] 1,000만원 투자 기준 기간별 비용 예시는 1년·2년·3년·5년·10년 기간별 비용 예시 열로 나뉘어 있습니다.
[근거] 0a1c8fece530be69-table-f26fac86b527
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p46-013

- Source seed: `seed-p46-013`
- Requirements: `product.total_fee`
- Evidence: `a55a5901a9b344c6-table-08bcb0a8c4ea`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5127420083 다음 KR5127420045 중 후자로 적힌 상품의 연간 총보수·비용은 어느 표의 어떤 항목으로 확인하나요?

**Completion**

```text
[답변] 후자는 KR5127420045입니다. 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.
[근거] a55a5901a9b344c6-table-08bcb0a8c4ea
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p46-016

- Source seed: `seed-p46-016`
- Requirements: `DB.operation_party, DB.benefit_determination`
- Evidence: `4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
DB제도는 적립 재원을 누가 운용하고, 퇴직급여 계산에는 평균임금과 어떤 기간이 함께 반영되나요?

**Completion**

```text
[답변] DB제도에서는 회사가 적립금을 운용합니다. 퇴직급여 계산에는 퇴직 전 평균임금 30일분과 계속근로기간이 함께 반영됩니다.
[근거] 4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p47-008

- Source seed: `seed-p47-008`
- Requirements: `product.risk_grade.current, product.risk_grade.change_possibility`
- Evidence: `c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113420012는 현재 몇 등급 위험 상품이며, 한번 정해진 등급이라 이후에도 바뀌지 않는다고 봐도 되나요?

**Completion**

```text
[답변] 현재 5등급(낮은 위험)입니다. 문서상 운용실적·시장 상황 등에 따라 변경될 수 있음으로 안내됩니다.
[근거] c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p47-010

- Source seed: `seed-p47-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047 설명서에서 1년 기준 총보수·비용률을 보려면 어떤 표와 항목을 찾아야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표에서 총보수·비용 또는 합성총보수·비용 항목을 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p47-014

- Source seed: `seed-p47-014`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027의 보수 중 판매수수료와 별도로 연간 총보수·비용을 확인할 때 문서의 어느 칸을 봐야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-002

- Source seed: `seed-p48-002`
- Requirements: `DC.employer_contribution`
- Evidence: `fc71bcf7cc90f68d-table-c1ac92bf85cc`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
확정기여형 퇴직연금에서 회사 부담금은 매년 임금총액보다 적게 정할 수 있나요? 법정 기준을 알려주세요.

**Completion**

```text
[답변] 확정기여형 퇴직연금의 회사 부담금 법정 기준은 연간 임금총액의 12분의 1 이상입니다.
[근거] fc71bcf7cc90f68d-table-c1ac92bf85cc
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-005

- Source seed: `seed-p48-005`
- Requirements: `retirement_income.IRP_transfer.tax_timing`
- Evidence: `7878a3be5806fef4-table-a3623398dbaa`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
퇴직급여 일시금을 IRP에 넣고 나중에 연금으로 받는 경우, 세금은 적립 중과 연금 수령 중 언제 붙나요?

**Completion**

```text
[답변] 퇴직급여 일시금을 IRP로 옮긴 뒤에는 운용 중 과세이연됩니다. 세금은 연금 수령 시마다 과세됩니다.
[근거] 7878a3be5806fef4-table-a3623398dbaa
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-008

- Source seed: `seed-p48-008`
- Requirements: `product.risk_grade.current, product.risk_grade.change_possibility`
- Evidence: `c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113420012의 지금 위험등급은 무엇이며, 장래에도 문서상 같은 등급으로 보장된다고 할 수 있나요?

**Completion**

```text
[답변] 현재 5등급(낮은 위험)입니다. 운용실적·시장 상황 등에 따라 변경 가능합니다.
[근거] c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-009

- Source seed: `seed-p48-009`
- Requirements: `product.risk_grade.historical`
- Evidence: `9175b4d6847de4c3-table-012d76a0b2f1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111이 과거에 위험등급을 바꾼 이유와 변경 전후 수준은 설명서의 어떤 기록에서 알 수 있나요?

**Completion**

```text
[답변] 변경 전·후 위험등급과 변경 사유를 포함한 변경 이력 표를 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-012d76a0b2f1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-010

- Source seed: `seed-p48-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047의 매년 드는 총보수·비용률은 설명서에서 어떤 표의 어떤 열을 기준으로 읽어야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 기준으로 읽어야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-011

- Source seed: `seed-p48-011`
- Requirements: `product.period_cost`
- Evidence: `9175b4d6847de4c3-table-9ed35d020b3b`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111을 1,000만원 기준으로 3년 들고 있을 때의 비용은 어느 비용 예시 표의 어느 기간 열에서 보나요?

**Completion**

```text
[답변] 투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-9ed35d020b3b
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## positive_draft-p48-014

- Source seed: `seed-p48-014`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027의 판매수수료가 아닌 연간 총보수·비용은 지급비율 표의 어느 항목인가요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 항목입니다. 판매수수료와 구분해야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-010

- Source seed: `seed-p45-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047에서 1,000만원 보유기간별 비용이 아니라 매년 적용되는 총보수·비용률은 어디에서 봐야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 구분해 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-011

- Source seed: `seed-p45-011`
- Requirements: `product.period_cost`
- Evidence: `9175b4d6847de4c3-table-9ed35d020b3b`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111의 연간 총보수율이 아니라 1,000만원을 3년 보유한 비용 예시는 어느 열에서 보나요?

**Completion**

```text
[답변] 1,000만원 투자 시 투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-9ed35d020b3b
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-013

- Source seed: `seed-p45-013`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR510902511M은 제외하고 KR5111420047의 연간 총보수·비용률만 보려면 무엇을 확인하나요?

**Completion**

```text
[답변] 두 번째 상품은 KR5111420047입니다. 지급비율(연간, %)의 총보수·비용 항목을 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-015

- Source seed: `seed-p45-015`
- Requirements: `product.period_cost`
- Evidence: `1294013a2a74e0a4-table-0689dcaed960`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5110501016의 위험등급이 아니라 1,000만원 투자 기간별 비용 표에는 어떤 보유기간 열이 있나요?

**Completion**

```text
[답변] 기간별 비용 예시는 1년·2년·3년·5년·10년 보유 기간별 비용 예시 열로 제시됩니다.
[근거] 1294013a2a74e0a4-table-0689dcaed960
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-016

- Source seed: `seed-p45-016`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027에서 판매수수료가 아니라 연간 총보수·비용을 보려면 어떤 항목을 읽어야 하나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표에서 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해서 읽어야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p45-018

- Source seed: `seed-p45-018`
- Requirements: `DB.operation_party, DB.benefit_determination`
- Evidence: `4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
DB형의 운용 주체와 퇴직급여 산정 기준을 DC형 기준과 섞지 말고 알려주세요.

**Completion**

```text
[답변] DB형은 회사가 적립금을 운용합니다. 퇴직급여 산정에는 퇴직 전 평균임금 30일분과 계속근로기간으로 퇴직급여 산정하는 기준이 함께 쓰입니다.
[근거] 4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p46-009

- Source seed: `seed-p46-009`
- Requirements: `product.period_cost`
- Evidence: `0a1c8fece530be69-table-f26fac86b527`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420016의 연간 보수율 말고 1,000만원 기준 기간별 비용 예시는 어떤 보유기간 열을 보나요?

**Completion**

```text
[답변] 1,000만원 투자 기준 기간별 비용 예시는 1년·2년·3년·5년·10년 기간별 비용 예시 열로 나뉘어 있습니다.
[근거] 0a1c8fece530be69-table-f26fac86b527
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p46-013

- Source seed: `seed-p46-013`
- Requirements: `product.total_fee`
- Evidence: `a55a5901a9b344c6-table-08bcb0a8c4ea`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
두 상품 중 KR5127420045만 대상으로, 판매수수료가 아닌 연간 총보수·비용은 어디에서 확인하나요?

**Completion**

```text
[답변] 후자는 KR5127420045입니다. 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다.
[근거] a55a5901a9b344c6-table-08bcb0a8c4ea
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p46-016

- Source seed: `seed-p46-016`
- Requirements: `DB.operation_party, DB.benefit_determination`
- Evidence: `4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
DB제도에서 회사 운용 여부와 퇴직급여 계산의 기간 기준을 함께 알려주세요.

**Completion**

```text
[답변] DB제도에서는 회사가 적립금을 운용합니다. 퇴직급여 계산에는 퇴직 전 평균임금 30일분과 계속근로기간이 함께 반영됩니다.
[근거] 4607500e74afcdf8-table-6f164502cbce, fc71bcf7cc90f68d-table-fc470df2b580
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p47-008

- Source seed: `seed-p47-008`
- Requirements: `product.risk_grade.current, product.risk_grade.change_possibility`
- Evidence: `c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113420012의 현재 위험등급과 향후 변경 가능성을 원금보장 여부와 구분해 알려주세요.

**Completion**

```text
[답변] 현재 5등급(낮은 위험)입니다. 문서상 운용실적·시장 상황 등에 따라 변경될 수 있음으로 안내됩니다.
[근거] c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p47-010

- Source seed: `seed-p47-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047의 3년 비용 예시가 아니라 연간 총보수·비용률의 표와 항목은 무엇인가요?

**Completion**

```text
[답변] 지급비율(연간, %) 표에서 총보수·비용 또는 합성총보수·비용 항목을 확인해야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p47-014

- Source seed: `seed-p47-014`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027에서 판매수수료와 구별되는 연간 총보수·비용은 지급비율 표의 어느 항목인가요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 항목을 확인해야 합니다. 판매수수료와 구분해야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-002

- Source seed: `seed-p48-002`
- Requirements: `DC.employer_contribution`
- Evidence: `fc71bcf7cc90f68d-table-c1ac92bf85cc`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
DC형 회사 부담금의 임의 설정 여부가 아니라 법정 최저 기준만 알려주세요.

**Completion**

```text
[답변] 확정기여형 퇴직연금의 회사 부담금 법정 기준은 연간 임금총액의 12분의 1 이상입니다.
[근거] fc71bcf7cc90f68d-table-c1ac92bf85cc
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-005

- Source seed: `seed-p48-005`
- Requirements: `retirement_income.IRP_transfer.tax_timing`
- Evidence: `7878a3be5806fef4-table-a3623398dbaa`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
IRP 이체 직후 과세 여부가 아니라 운용 중과 연금 수령 중의 과세 시점만 구분해 알려주세요.

**Completion**

```text
[답변] 퇴직급여 일시금을 IRP로 옮긴 뒤에는 운용 중 과세이연됩니다. 세금은 연금 수령 시마다 과세됩니다.
[근거] 7878a3be5806fef4-table-a3623398dbaa
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-008

- Source seed: `seed-p48-008`
- Requirements: `product.risk_grade.current, product.risk_grade.change_possibility`
- Evidence: `c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113420012의 현재 위험등급과 미래 변경 가능성을 각각 알려주세요.

**Completion**

```text
[답변] 현재 5등급(낮은 위험)입니다. 운용실적·시장 상황 등에 따라 변경 가능합니다.
[근거] c61c1c27df94646e-table-52d53a2b5d36, c61c1c27df94646e-paragraph_group-209bb3d672f2
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-009

- Source seed: `seed-p48-009`
- Requirements: `product.risk_grade.historical`
- Evidence: `9175b4d6847de4c3-table-012d76a0b2f1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111의 현재 등급이 아니라 과거 변경 전후 등급과 변경 사유는 어느 기록에서 확인하나요?

**Completion**

```text
[답변] 변경 전·후 위험등급과 변경 사유를 포함한 변경 이력 표를 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-012d76a0b2f1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-010

- Source seed: `seed-p48-010`
- Requirements: `product.total_fee`
- Evidence: `1bfc399c9b3d6a67-table-d384a980cda1`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5111420047의 기간별 투자비용과 구분되는 연간 총보수·비용률은 무엇을 기준으로 읽나요?

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 또는 합성총보수·비용 항목을 기준으로 읽어야 합니다.
[근거] 1bfc399c9b3d6a67-table-d384a980cda1
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-011

- Source seed: `seed-p48-011`
- Requirements: `product.period_cost`
- Evidence: `9175b4d6847de4c3-table-9ed35d020b3b`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5113450111의 연간 비용률이 아니라 1,000만원을 3년 보유한 비용 예시는 어느 표의 어느 열인가요?

**Completion**

```text
[답변] 투자기간별 총보수·비용 예시 표의 3년 열을 확인해야 합니다.
[근거] 9175b4d6847de4c3-table-9ed35d020b3b
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```

## contrastive_draft-p48-014

- Source seed: `seed-p48-014`
- Requirements: `product.total_fee`
- Evidence: `37c0cd9b61ebeb19-table-57d54383176e`
- Review status: `pending`
- Reviewer note: (empty)

**질문**  
KR5114420027에서 판매수수료를 답하지 말고 연간 총보수·비용 항목만 알려주세요.

**Completion**

```text
[답변] 지급비율(연간, %) 표의 총보수·비용 항목입니다. 판매수수료와 구분해야 합니다.
[근거] 37c0cd9b61ebeb19-table-57d54383176e
[유의사항] 제공된 원본 근거와 질문에서 요구한 field만 사용했습니다.
```
