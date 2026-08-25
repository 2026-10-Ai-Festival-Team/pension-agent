# P36-B Generalized Canonicalization Fix

## Scope

- P36-A의 frozen pre-HCX failure attribution 뒤 수행한 development regression이다.
- HCX 호출은 **0회**이며, prompt, HCX 모델, provider pacing, citation validator, corpus, 전역 BM25 파라미터는 변경하지 않았다.
- P36 question ID나 질문 전체 문자열을 조건으로 사용하지 않았다.
- P36은 이미 development/regression set이며, 이 결과는 fresh generalization 증거가 아니다.

## Generalized changes

1. **Component canonicalization**
   - Subject: `개인연금 저축계좌 → 연금저축`, `개인형 퇴직연금 → IRP`
   - Action/event: 퇴직 전·재직 중 일부 인출, ISA 종료/만기, 환매 없는 사업자 변경
   - Field: 투자위험 분류·위험 단계, 등급 변경 가능성, 지수 추종, 주식 투자 비중, 기간별 비용 예시
   - Modifier: 배수/반대 방향 ETF, 일반계좌 scope, 교육 책임·주기·위탁
2. **Product field ontology**
   - `risk_grade`, `risk_grade_changeability`, `investment_strategy`, `investment_target`, `total_fee`, `example_cost`를 별도 requirement로 유지했다.
3. **Closed factual selection guard**
   - 두 명시적 상품코드와 객관 field를 비교해 낮은 위험/비용 대상을 고르는 질문은 suitability recommendation이 아니라 Closed factual comparison으로 분류했다.
4. **P36-007 유형 matcher scope**
   - 연금저축/IRP 인출 비교의 세 slot은 하나의 account-specific evidence bundle을 공유한다.
   - ISA FAQ처럼 계좌 이름만 언급한 문장이 연금저축 인출 범위의 대체 근거가 되지 않도록 `사유무관/사유와 무관` 직접 사실을 요구했다.

## P36-B pre-HCX result

- Manifest SHA-256: `6ee433b5fbe323be49889c2c13690d5fb96874a5069ac5e7b40ce6a5621913a8`
- Semantic requirement coverage: **18/18**
- Evidence sufficiency: **18/18**
- Selected evidence original + primary: **18/18**
- Exact gold: **13/18**
- Current semantic equivalent: **5/18**
- Exact + equivalent: **18/18**
- Partial / wrong-scope / evidence drift: **0 / 0 / 0**
- HCX calls: **0**

The five semantic-equivalent decisions are tied to the P36-B current selected chunk IDs in `evaluation/regressions/p36b_current_evidence_revalidation.json`; they must be re-adjudicated if selection changes.

## Deterministic regression

- Full test suite: **272 passed**
- Closed Core evidence sufficiency: **46/46**
- Product subject-field binding: **10/10**
- P32 deterministic behavior: **25/25**; P15/P31 newly blocked cases: **0**
- P33 deterministic expected behavior: **25/25**; first-turn policy wording: **7/7**
- P34 current evidence: **18/18 exact + equivalent**, partial/wrong-scope **0/0**
- P35 current evidence: **18/18 exact + equivalent**, partial/wrong-scope **0/0**

P33's separate manifest exact-ID overlap remains 13/18. It is a stricter metadata comparison than semantic-equivalence adjudication and is retained as a provenance/relevance backlog; it is not silently converted into a pass by P36-B.

## Decision

**P36-B regression Go.** P36 now meets the Closed pre-HCX preparation contract as a development set. Freeze this candidate and create a fully new P37 Closed factual holdout before any fresh-generalization claim. Do not use a P36 re-score as proof of generalization.
