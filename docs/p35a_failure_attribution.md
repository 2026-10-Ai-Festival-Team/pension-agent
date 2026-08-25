# P35-A Closed Pre-HCX Failure Attribution

## Frozen run 확인

- Frozen manifest SHA-256: `bb8eda3bd2f76bf8798b2ab6b531fc0ce6856a656a7f6fcd046363650fd03ad7`
- HCX 호출: **0** (FakeGenerator로 deterministic `prepare()`만 재현)
- Candidate production code modification: **없음**
- 기존 P35 manifest 및 `p35_closed_pre_hcx.json`은 수정하지 않았다.
- P35는 fresh holdout 자격을 잃었으며 이후 development/regression set으로만 사용한다.

## Pre-HCX 결과

- Frozen requirement-plan coverage: **13/18**
- Semantic requirement audit coverage: **12/18** (P35-013의 changeability slot 누락 포함)
- Frozen evidence sufficiency: **16/18**
- Original + primary selected evidence: **18/18**

## Primary owner summary

- `normalization_alias_miss`: **1**
- `normalization_semantic_miss`: **5**
- `planner_intent_miss`: **0**
- `planner_slot_miss`: **0**
- `planner_multi_requirement_miss`: **0**
- `planner_schema_variant`: **0**
- `subject_resolution`: **0**
- `retrieval_missing`: **1**
- `matcher_field_miss`: **1**
- `evidence_selection_miss`: **1**

Primary owner는 최초 실패 지점만 센다. 이후 plan/gate/source 문제는 secondary effect로만 기록했다.

## Source relevance

- Exact gold: **11**
- Semantic equivalent: **2**
- Partial: **4**
- Wrong scope: **1**

모든 non-exact 판정은 P35 frozen execution의 현재 selected IDs를 다시 확인해 수행했다. P33/P34 판정을 재사용하지 않았다.

### Current non-exact evidence adjudications

- **P35-005** — `partial`: 연금계좌에서 세금 납부 시점을 늦추는 일반 설명만 있어 일반계좌 과세 시점과 면제 아님을 함께 직접 비교하지 못한다.
- **P35-007** — `wrong_scope`: 선택된 DC 해외 ETF 과세 문장과 일반 DB/DC 설명은 연금저축·IRP 인출조건/법정사유 비교의 account scope를 직접 지지하지 않는다.
- **P35-012** — `semantic_equivalent`: 현재 DB/DC 비교표는 DB 회사·DC 근로자 운용 및 평균임금 대 부담금+운용손익 구조를 직접 지지하고, DC 지급 문단은 부담금 구조를 보강한다. gold와 chunk는 다르지만 subject·field·value·scope가 같다.
- **P35-013** — `partial`: 현재 표는 KR510902773M의 3등급 값을 직접 지지하지만, 운용실적·시장 상황에 따라 등급이 변경될 수 있다는 두 번째 requirement를 담지 않는다.
- **P35-016** — `semantic_equivalent`: 각 source product의 3등급·2등급 위험등급을 직접 제시한다. gold paragraph와 달라도 두 subject, field, value와 비교 scope를 모두 충족한다.
- **P35-017** — `partial`: final selected evidence가 없으므로 두 상품 위험등급 requirement를 하나도 지지하지 못한다. 다른 account/product를 잘못 선택한 wrong-scope가 아니라 selection 부재다.
- **P35-018** — `partial`: KR5120420091의 현재 6등급은 직접 지지하지만 KR5120420039 선택 표의 5등급은 과거 변경 내역이다. 질문의 설명서 기준 현재 등급 requirement를 direct/equivalent하게 확정하지 못한다.

## Failed case analysis

### P35-001 — `normalization_semantic_miss`

- 질문: DB/DC에서 회사가 돈을 굴려주는 쪽과 퇴직급여를 계산하는 방식, 그리고 DC 회사 부담금 기준을 한 번에 구분해 주세요.
- Gold requirements: DB·DC 급여 결정 방식 / DB·DC 운용 주체 / DC 회사 부담금 기준
- Generated slots: db_benefit, dc_benefit
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: 4607500e74afcdf8-paragraph_group-fd0d4e7d80e6
- Source relevance: `exact_gold` — 선택 evidence에 manifest gold chunk가 있으며 frozen run 기준 factual coverage를 직접 지지한다.
- 판정: DB/DC와 급여 계산은 인식해 benefit plan을 만들었지만, 구어체 ‘돈을 굴려주는 쪽’이 operation_party로 정규화되지 않아 운용 주체 requirement가 생성되지 않았다.
- Downstream: planner_multi_requirement_miss: benefit slots만 생성되어 operation slot이 빠짐

### P35-004 — `normalization_alias_miss`

- 질문: 연저만 납입할 때와 연저+IRP로 넣을 때 세액 공제한도는 왜 따로 계산하며 각각 얼마인가요?
- Gold requirements: 연금저축 단독 세액공제 대상 한도 / IRP 포함 합산 세액공제 대상 한도
- Generated slots: 없음
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: 5a8516a0215f8754-slide-bbf8ab17ae0d, 5a8516a0215f8754-slide-c1523d81c161, ef05c9c97fbadd27-table-6cb74dcb5e83, ef05c9c97fbadd27-paragraph_group-c169d907b699, 2578707c6323de46-paragraph_group-1daf64189064, ef05c9c97fbadd27-paragraph_group-789430c51fb1, 2578707c6323de46-table-0f2ea0cfdcac, 7cce439d30d5a8b0-paragraph_group-f2f6ed313014, cb50751d7ccd46bf-paragraph_group-c345b8d0ff3a, eef705af2a7c3c57-paragraph_group-c3bde8f09076
- Source relevance: `exact_gold` — 선택 evidence에 manifest gold chunk가 있으며 frozen run 기준 factual coverage를 직접 지지한다.
- 판정: 현재 entity extraction은 ‘연금저축’만 account로 인식한다. IRP만 추출된 상태에서는 연금저축·IRP 한도 비교 schema의 두 account predicate가 성립하지 않는다.
- Downstream: planner_intent_miss: 연금저축+IRP 비교 predicate가 충족되지 않음; gate_false_reject

### P35-005 — `normalization_semantic_miss`

- 질문: 일반 계좌보다 연금계좌에서 세금을 나중에 낸다는 말은 세금이 없어지는 것인가요, 아니면 내는 시점만 미뤄지는 것인가요?
- Gold requirements: 일반계좌 과세 시점 / 연금계좌 과세이연의 조건·시점
- Generated slots: 없음
- Candidate에 gold/equivalent 존재: **False**
- Selected evidence: 7878a3be5806fef4-paragraph_group-d24f4b2854ed, eec10989c7067926-paragraph_group-72065e97ce5d, ae22159be59440b6-paragraph_group-8d64cc53348b, 13621d38202e2fc3-table-5431011b44b5, 13621d38202e2fc3-table-c64398404ba4, 13621d38202e2fc3-paragraph_group-ae6b841e4074, 5a8516a0215f8754-slide-bbf8ab17ae0d, eec10989c7067926-paragraph_group-15cf127eb9b9, 5a8516a0215f8754-slide-c1523d81c161, 4d6edde4fa5b925d-paragraph_group-000adad54805
- Source relevance: `partial` — 연금계좌에서 세금 납부 시점을 늦추는 일반 설명만 있어 일반계좌 과세 시점과 면제 아님을 함께 직접 비교하지 못한다.
- 판정: 질문은 면제와 과세시점 이연을 구분하지만 현재 canonical form은 ‘과세이연’ intent로 바꾸지 못해 simple retrieval 경로로 남았다.
- Downstream: planner_intent_miss: tax_deferral comparison plan 미생성

### P35-007 — `matcher_field_miss`

- 질문: 연금저축처럼 IRP도 필요한 금액만 중간에 찾을 수 있나요? 중도 인출사유와 세금 처리의 차이도 같이 알려주세요.
- Gold requirements: 연금저축 인출 범위 / IRP 법정 중도인출 사유 / 인출 과세 처리
- Generated slots: pension_savings_withdrawal_scope, irp_withdrawal_legal_grounds_comparison, account_withdrawal_tax_treatment
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: de4f8448134189df-paragraph_group-56c3e7dd9332, 4607500e74afcdf8-paragraph_group-fd0d4e7d80e6
- Source relevance: `wrong_scope` — 선택된 DC 해외 ETF 과세 문장과 일반 DB/DC 설명은 연금저축·IRP 인출조건/법정사유 비교의 account scope를 직접 지지하지 않는다.
- 판정: 연금저축·IRP 인출 비교 plan과 gold withdrawal chunks는 모두 candidate에 있다. 그러나 matcher의 넓은 인출/과세 term이 DC 해외 ETF 과세 문장과 일반 DB/DC 문단을 선택해 IRP 법정사유·계좌별 과세 requirement를 잘못 충족으로 판단했다.
- Downstream: source_relevance_wrong_scope; evidence_selection_contains_wrong_scope_context

### P35-008 — `normalization_semantic_miss`

- 질문: DC에 쌓인 돈을 중간에 찾기 전에는 법정 사유만 확인하면 되나요, 신청서와 증명 서류도 챙겨야 하나요?
- Gold requirements: DC 중도인출 가능 사유 / 신청 절차·증빙
- Generated slots: 없음
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: fc71bcf7cc90f68d-paragraph_group-4d522b97d9ef, 93b9b09c57458c3b-paragraph_group-fd7b1d062026, fc71bcf7cc90f68d-paragraph_group-72acff87b157, dde0fd3c595c051a-table-1678c28588e6, ee3b84ad68394b49-table-df729eabdb92, 4607500e74afcdf8-table-6f164502cbce, 04782a392f49293e-paragraph_group-37b3740ca9e9, 2ce564b5ddde4f21-paragraph_group-fc907f93763a, dc5f01c34172a900-table-e57a45f01a30, e8d7e6a69504e042-paragraph_group-f8a143ed15a7
- Source relevance: `exact_gold` — 선택 evidence에 manifest gold chunk가 있으며 frozen run 기준 factual coverage를 직접 지지한다.
- 판정: 현재 normalization은 ‘중간에 꺼내/빼’만 중도인출로 바꾸며 ‘중간에 찾기’와 ‘증명 서류’를 canonical withdrawal-procedure 표현으로 바꾸지 못한다.
- Downstream: planner_multi_requirement_miss: withdrawal procedure schema 미생성

### P35-009 — `normalization_semantic_miss`

- 질문: ISA 만기 돈을 연저나 IRP로 넘길 때 며칠 안에 해야 하고, 세액공제는 어떤 계산으로 더 인정되나요?
- Gold requirements: ISA 만기자금 이전 기한 / 추가 세액공제 계산 기준·한도
- Generated slots: 없음
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: 5a8516a0215f8754-slide-bbf8ab17ae0d, 5a8516a0215f8754-slide-d1c93150f64c, 2578707c6323de46-table-0f2ea0cfdcac, ae22159be59440b6-table-433001f3f808, ae22159be59440b6-paragraph_group-ec1f3e9c5bc1, 5a8516a0215f8754-slide-c1523d81c161, 2578707c6323de46-paragraph_group-c9eaeb3944b5, ae22159be59440b6-paragraph_group-8afcfabdd378, ef05c9c97fbadd27-paragraph_group-c169d907b699, daee1e8f1b1753ed-paragraph_group-937bad550701
- Source relevance: `exact_gold` — 선택 evidence에 manifest gold chunk가 있으며 frozen run 기준 factual coverage를 직접 지지한다.
- 판정: IRP entity가 이미 추출되어 account scope는 충족한다. 하지만 ISA rule의 transfer verb 집합에 ‘넘길’이 없어 ISA 만기 이전 intent 자체가 만들어지지 않았다.
- Downstream: planner_intent_miss: ISA maturity transfer plan 미생성; normalization_alias_miss: 연저 미정규화는 존재하지만 IRP entity가 있어 최초 차단 원인은 아님

### P35-013 — `normalization_semantic_miss`

- 질문: KR510902773M 위험등급몇등급인가요? 시장 상황이 바뀌어도 이 등급은 계속 고정인가요?
- Gold requirements: KR510902773M 위험등급 / 위험등급 변경 가능성
- Generated slots: KR510902773M:risk_grade
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: cf922cacac95fad9-table-8d0be7d0b37c
- Source relevance: `partial` — 현재 표는 KR510902773M의 3등급 값을 직접 지지하지만, 운용실적·시장 상황에 따라 등급이 변경될 수 있다는 두 번째 requirement를 담지 않는다.
- 판정: 위험등급 값 slot은 생성됐지만 ‘시장 상황이 바뀌어도 계속 고정’이라는 반대 표현이 변경 가능성 field로 정규화되지 않았다. 따라서 frozen slot-key metric의 pass와 달리 manifest의 두 번째 factual requirement는 빠져 있다.
- Downstream: planner_slot_miss; evaluator_slot_observability_gap: frozen expected_slot_keys에는 changeability가 없음

### P35-017 — `retrieval_missing`

- 질문: KR5114420022보다 KR5114450222가 더 비싼 위험등급인가요? 두 상품의 등급 표시를 근거로 비교해 주세요.
- Gold requirements: KR5114420022 위험등급 / KR5114450222 위험등급 / 낮은 위험 비교
- Generated slots: KR5114420022:risk_grade, KR5114450222:risk_grade
- Candidate에 gold/equivalent 존재: **False**
- Selected evidence: 없음
- Source relevance: `partial` — final selected evidence가 없으므로 두 상품 위험등급 requirement를 하나도 지지하지 못한다. 다른 account/product를 잘못 선택한 wrong-scope가 아니라 selection 부재다.
- 판정: 두 product code 결속과 각 risk_grade slot 생성은 성공했다. 그러나 candidate 20개는 두 source의 성과·법률·관리 문단만 포함하고, 어느 product의 위험등급 direct/equivalent chunk도 포함하지 않아 matcher와 final selection 단계에 도달하지 못했다.
- Downstream: matcher_field_miss_not_reached: risk-grade chunk가 candidate에 없음; gate_false_reject

### P35-018 — `evidence_selection_miss`

- 질문: KR5120420039와 KR5120420091 중 설명서 기준으로 더 안전 쪽 등급으로 적힌 것은 무엇이며 각각 몇 등급인가요?
- Gold requirements: KR5120420039 위험등급 / KR5120420091 위험등급 / 상대적 위험 비교
- Generated slots: KR5120420039:risk_grade, KR5120420091:risk_grade
- Candidate에 gold/equivalent 존재: **True**
- Selected evidence: fc3cd93441450fa8-table-3c68497fd9d9, eefb7f7b407d91de-paragraph_group-e41211088478
- Source relevance: `partial` — KR5120420091의 현재 6등급은 직접 지지하지만 KR5120420039 선택 표의 5등급은 과거 변경 내역이다. 질문의 설명서 기준 현재 등급 requirement를 direct/equivalent하게 확정하지 못한다.
- 판정: 두 상품 subject와 risk_grade slots는 정확하며 candidate에는 KR5120420039의 현재 5등급 direct chunks도 있다. 하지만 final selection은 더 높은 lexical score의 과거 변경내역 표를 골라, 설명서 기준 현재 등급 requirement를 충족하지 못했다.
- Downstream: source_relevance_partial: KR5120420039의 선택 표는 과거 위험등급 변경 내역만 제시

## Generalization diagnosis

- **Semantic normalization**이 가장 이른 반복 failure다. ‘굴려주는 쪽’, ‘세금을 나중에 낸다’, ‘중간에 찾기’, ‘넘길’, ‘계속 고정’이 각각 운용주체·과세이연·중도인출/증빙·ISA 이전·위험등급 변경 가능성으로 canonicalize되지 않았다.
- **Lexical alias**는 `연저 → 연금저축` 한 건에서 독립적인 최초 원인이었다. P35-009의 `연저`는 IRP가 이미 있어 ISA rule의 account predicate를 막지는 않았으므로 secondary로만 기록했다.
- **Matcher scope binding**은 P35-007에서 account-specific withdrawal evidence 대신 DC 해외 ETF/일반 문단을 선택했다. candidate에는 적합한 IRP·연금저축 근거가 있었다.
- **Product retrieval**은 P35-017에서 product code와 risk-grade slot은 정확했지만 source-level BM25 후보가 위험등급 본문까지 도달하지 못했다.
- P35-013은 frozen slot-key metric이 risk_grade만 보아 pass로 집계했으나, manifest의 changeability requirement는 실제로 누락됐다. 이는 production pass가 아니라 evaluation observability gap이다.

## P35-B recommendations (수정하지 않음)

1. 표현별 질문 패치가 아니라 `surface phrase → canonical concept/entity/field` normalization layer를 설계한다. 이 레이어는 연금저축 alias, 과세이연, 중도인출+증빙, ISA 이전, 운용주체, 위험등급 변경 가능성을 각각 canonical representation으로 넘겨야 한다.
2. requirement builder는 canonical representation에서 multi-requirement decomposition을 수행해, 조건/절차/증빙과 비교 대상별 동일 field를 별도 slot으로 생성한다.
3. withdrawal matcher는 `account subject + field + value/condition`을 함께 요구해 DC 해외 ETF 과세 문장이 IRP 법정사유·계좌별 인출 과세 근거를 대체하지 못하게 한다.
4. product-field retrieval은 code document의 일반 문단을 반복 확장하기보다 risk-grade field가 있는 첫 페이지/표 chunk를 후보로 보장하는 별도 field recall을 검증한다.
5. 평가에서는 human-readable `required_requirements`와 machine slot keys의 semantic coverage를 함께 저장해 P35-013 같은 false pass를 방지한다.

## Go / No-Go

**No-Go.** P35 pre-HCX는 semantic requirement audit 12/18이며, source relevance도 exact-or-equivalent 13/18에 그친다. HCX를 호출하지 않는다. P35를 수정 후 점수로 일반화 증거로 쓰지 않으며, 일반화 검증은 향후 P36 fresh Closed holdout에서 수행한다.
