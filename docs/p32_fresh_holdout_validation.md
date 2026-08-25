# P32: Fresh Holdout Validation

P31 v2 코드를 변경하지 않고, 실행 전 동결한 25문항(답변 가능 22 / unsupported 3)을 HCX-007 Native Structured Outputs·6초 pacing으로 평가했다.

## 결과

- Strict Useful: **9/22** (Go 기준 ≥75%)
- Semantic correctness: **9/22**
- Unsupported safety: **3/3**
- False rejection: **3** — P32-009, P32-014, P32-025
- Unsafe pass: **1** — P32-019
- Financial/recommendation policy regression: **7** — P32-009, P32-014, P32-016, P32-017, P32-018, P32-019, P32-025

## 운영 계약

- provider attempts: 16, HTTP 200: 16, 429/5xx/timeout/retry exhaustion: 0/0/0/0
- JSON/schema 및 citation validator failure: 0

## 판정

**No-Go.** P31 v2는 기존 Full-40에서는 강했지만 이 independent holdout의 strict-useful·policy-safety 기준을 충족하지 못했다. 특히 상품 기간별 비용 예시와 연간 보수의 field boundary, 복합 제도 설명, 조건부 추천/세무정책에서 일반화 부족이 확인됐다. 이 결과를 본 뒤 Agent 규칙은 변경하지 않았다.
