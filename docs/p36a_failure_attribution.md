# P36-A Closed Pre-HCX Failure Attribution

## Frozen-run integrity

- Manifest SHA-256: `6ee433b5fbe323be49889c2c13690d5fb96874a5069ac5e7b40ce6a5621913a8`
- HCX calls: **0**; this diagnostic only reads the frozen pre-HCX artifact.
- Agent, retriever, matcher, gate, prompt, policy, and evaluator behaviour were **not changed**.
- P36 is now a development/regression set; it must not be reused as generalization evidence after a fix.

## Result

- Semantic requirement coverage: **5/18**
- Frozen evidence sufficiency: **13/18**
- Original + primary provenance: **18/18**
- Source relevance among fully planned cases: exact **1**, equivalent **3**, partial **0**, wrong-scope **1**.

## First-failure owners

- `normalization_alias_miss`: **1**
- `normalization_semantic_miss`: **7**
- `canonical_field_miss`: **5**
- `matcher_field_miss`: **1**

The 13 semantic requirement failures occur before retrieval ranking: 8 are entity/operation/intent normalization failures and 5 are product field canonicalization failures. P36-007 is the separate matcher/source-scope failure after a correct plan.

## Source-relevance audit

Only the five rows with full semantic requirement plans are source-adjudicated. Four pass with exact/equivalent evidence; P36-007 is wrong-scope. Rows whose requirements were not formed are not counted as source-relevance passes merely because they share a document or an exact gold chunk.

- **P36-001** — `semantic_equivalent`: 현재 DB/DC 비교표가 운용 주체, 급여 결정 방식, DC 회사 부담금 구조를 함께 직접 지지한다. gold paragraph와 달라도 subject·field·value·scope가 동일하다.
- **P36-005** — `semantic_equivalent`: 현재 선택 표와 설명 문단이 일반계좌와 연금계좌의 과세 시점 및 과세이연 조건을 직접 비교한다. gold IDs와 달라도 같은 tax timing facts를 지지한다.
- **P36-007** — `wrong_scope`: 세 번째 문단은 인출 과세 일부를 지지할 수 있지만 앞의 두 selected evidence는 ISA 문서의 연금저축 언급·ISA 이전 문단이다. 연금저축 인출 범위와 IRP 법정 중도인출 사유를 대체할 수 없다.
- **P36-012** — `semantic_equivalent`: 현재 DB/DC 비교표가 운용 주체, 급여 결정 방식, DC 부담금 구조를 직접 제시해 db_dc_benefit_calculation schema와 의미적으로 동등하다.

## Failed-case attribution

### P36-002 — `normalization_semantic_miss`

- Required facts: 교육 실시 주체 / 최소 실시 주기 / 위탁 가능 여부
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 가입자 교육 책임·실시 주체 / 최소 연간 주기 / 전문기관 위탁 가능 여부
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: ‘책임지고 시행’, ‘1년에’, ‘전문기관에 위임’이 participant_education canonical intent와 세 factual slot으로 정규화되지 않아 simple fallback으로 남았다.

### P36-003 — `normalization_semantic_miss`

- Required facts: 퇴직연금 ETF 직접매매 범위 / 레버리지·인버스 제한
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 두 배로 움직임 → 레버리지 ETF / 반대로 움직임 → 인버스 ETF
- Evidence sufficient: **False**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: DC·IRP ETF 직접매매 entity는 보이지만 배수·반대 추종 표현이 leverage/inverse restriction concept로 정규화되지 않아 restriction plan과 field query가 생성되지 않았다.

### P36-004 — `normalization_alias_miss`

- Required facts: 연금저축 단독 세액공제 대상 한도 / IRP 포함 합산 세액공제 대상 한도
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 개인연금 저축계좌 → 연금저축 / 개인형퇴직연금 → IRP
- Evidence sufficient: **False**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 질문의 두 계좌 표현이 canonical account entity로 결속되지 않아 연금저축 단독과 IRP 포함 한도를 각각 요구하는 tax comparison schema가 발동하지 않았다.

### P36-006 — `normalization_semantic_miss`

- Required facts: 일반계좌 매매차익·분배금 과세 / 연금계좌 과세 시점 / 문서의 조건·유의사항
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 국내 거래소 상장 해외 ETF / 계좌 밖 → 일반계좌 / 일반계좌 대 연금계좌 과세 비교
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 상품 성격과 ‘계좌 밖’의 일반계좌 scope가 foreign ETF account-tax comparison으로 함께 정규화되지 않아 복수 과세 requirement가 생성되지 않았다.

### P36-007 — `matcher_field_miss`

- Required facts: 연금저축 인출 범위 / IRP 법정 중도인출 사유 / 인출 과세 처리
- Actual category / slots: `pension_savings_irp_withdrawal_comparison` / pension_savings_withdrawal_scope, irp_withdrawal_legal_grounds_comparison, account_withdrawal_tax_treatment
- Missing canonical concepts: 없음
- Evidence sufficient: **True**; source relevance: `wrong_scope`
- Attribution: 연금저축·IRP 인출 비교 plan과 직접 gold chunks가 candidate에 있었지만, matcher/selection은 ISA 문서의 연금저축 언급과 ISA 이전 문단을 계좌별 인출 범위·IRP 법정 사유 근거로 선택했다. account + field + scope 결속 실패다.

### P36-008 — `normalization_semantic_miss`

- Required facts: DC 중도인출 가능 사유 / 신청 절차·증빙
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 퇴직 전에 꺼내기 → DC 중도인출 / 입증자료 → 신청 절차·증빙
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 중도인출의 간접 표현과 입증자료가 withdrawal condition/procedure concepts로 연결되지 않아 DC 법정 사유와 증빙을 분리한 plan이 만들어지지 않았다.

### P36-009 — `normalization_semantic_miss`

- Required facts: ISA 만기자금 이전 기한 / 추가 세액공제 계산 기준·한도
- Actual category / slots: `None` / 없음
- Missing canonical concepts: ISA가 끝난 뒤 → ISA 만기 / 연금계좌로 이전 / 이전 후 추가 세액공제 계산
- Evidence sufficient: **False**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: ‘ISA가 끝난 뒤’가 만기 event로 canonicalize되지 않아 이전 기한과 추가 세액공제라는 두 requirement의 transfer schema가 발동하지 않았다.

### P36-010 — `normalization_semantic_miss`

- Required facts: 실물이전 정의·적용 범위 / DB·DC 신청 경로 / IRP 신청 경로
- Actual category / slots: `db_dc_conversion` / conversion_eligibility
- Missing canonical concepts: 환매하지 않고 사업자 변경 → 실물이전 / DB·DC와 IRP의 신청 경로 비교
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 표면상 사업자 변경이 DB→DC 전환 intent로 먼저 흡수됐다. 환매 없는 이전이라는 operation meaning과 account별 신청 경로가 in-kind transfer schema로 복원되지 않았다.

### P36-011 — `normalization_semantic_miss`

- Required facts: DC·IRP ETF 직접매매 범위 / 레버리지·인버스 ETF 제한
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 상승·하락 배수 추종 → 레버리지 ETF / 반대 방향 추종 → 인버스 ETF
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: P36-003과 같은 semantic normalization 공백이다. ETF 직접매매 limitation을 묻지만 배수/반대 추종 표현이 restriction field로 들어가지 않았다.

### P36-013 — `canonical_field_miss`

- Required facts: KR510902773M 위험등급 / 위험등급 변경 가능성
- Actual category / slots: `product_fields` / KR510902773M:investment_risk, KR510902773M:principal_loss_possible
- Missing canonical concepts: 투자위험 분류 → risk_grade / 시장 조건·운용 실적에 따른 조정 → risk_grade_changeability
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: product plan은 생성됐지만 위험 분류와 변경 가능성을 generic investment risk/principal loss로 축약했다. 현재 등급과 등급 변경 가능성은 서로 다른 factual fields여야 한다.

### P36-014 — `canonical_field_miss`

- Required facts: KR5127450215 투자전략 / KR5127450215 주식 관련 자산 투자비율
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 특정 지수 성과 반영 → investment_strategy / 주식 관련 자산 편입 비율 상한 → equity_allocation_limit
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 지수 성과와 편입비율 상한이 product strategy/asset allocation canonical fields로 결속되지 않아 product factual requirement가 생성되지 않았다.

### P36-015 — `canonical_field_miss`

- Required facts: KR510902773M C-e 총보수·비용 / KR510902773M 기간별 비용 예시 / 연간 비율과 기간별 예시의 차이
- Actual category / slots: `product_fields` / KR510902773M:total_fee
- Missing canonical concepts: 연간 총보수 비율 / 3년 보유 가정 비용 예시 / 두 비용 표현의 구분
- Evidence sufficient: **True**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 총보수는 인식됐지만 기간 보유 가정 금액이 cost_example field로 분리되지 않았다. 비율과 기간별 금액을 동일 cost field로 취급하면 질문의 field boundary requirement를 놓친다.

### P36-017 — `canonical_field_miss`

- Required facts: KR5114420022 위험등급 / KR5114450222 위험등급 / 낮은 위험 비교
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 몇 단계 위험 → risk_grade / 보수적으로 분류 → 상대적 낮은 위험 비교
- Evidence sufficient: **False**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: 두 product subject는 있으나 ‘몇 단계 위험’과 보수적 분류 표현이 risk_grade 및 comparative risk field로 정규화되지 않아 direct field retrieval query가 생성되지 않았다.

### P36-018 — `canonical_field_miss`

- Required facts: KR5120420039 위험등급 / KR5120420091 위험등급 / 상대적 위험 비교
- Actual category / slots: `None` / 없음
- Missing canonical concepts: 투자위험 분류 → risk_grade / 낮은 위험 단계 → relative risk comparison
- Evidence sufficient: **False**; source relevance: `not_evaluable_due_to_front_end_failure`
- Attribution: P36-017과 같은 product field normalization 공백이다. 두 상품의 risk-grade values와 낮은 쪽 비교가 별도 requirement로 만들어지지 않았다.

## Gate

**No-Go.** P36 misses the 18/18 pre-HCX criteria at semantic requirement coverage (5/18), evidence sufficiency (13/18), and source relevance (4/5 fully-planned cases; one wrong-scope). Do not invoke HCX. The next work must be a generalized Closed front-end fix, followed by a new fresh holdout rather than a P36 re-score being treated as generalization evidence.
