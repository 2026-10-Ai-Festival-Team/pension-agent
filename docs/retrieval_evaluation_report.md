# BM25 검색 기준선 평가

## 데이터셋

- 질문: 40개
- 답변 가능: 38개
- 답변 불가: 2개
- 개발/테스트: 30개 / 10개
- 모든 핵심 근거가 필요한 질문: 3개
- Corpus 청크: 23,421개
- Corpus SHA-256: `c61ac0d54dc9af5ee339460b8b810076f6df998c76f54983d667660a1e8eaead`
- BM25: BM25Okapi (`k1=1.5`, `b=0.75`); Corpus·질문·Top-k는 동일하고 토크나이저만 다름.

## 직접 답변 근거 결과

| 분할 | 토크나이저 | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---:|---:|---:|---:|---:|
| 전체 | Simple | 18.4% | 34.2% | 44.7% | 63.2% | 0.300 |
| 전체 | Kiwi | 7.9% | 26.3% | 42.1% | 52.6% | 0.213 |
| 개발 | Simple | 20.0% | 40.0% | 53.3% | 70.0% | 0.336 |
| 개발 | Kiwi | 10.0% | 33.3% | 50.0% | 63.3% | 0.261 |
| 테스트 | Simple | 12.5% | 12.5% | 12.5% | 37.5% | 0.167 |
| 테스트 | Kiwi | 0.0% | 0.0% | 12.5% | 12.5% | 0.031 |

## 전체 관련 근거 결과

| 토크나이저 | R@1 | R@3 | R@5 | R@10 |
|---|---:|---:|---:|---:|
| Simple | 18.4% | 34.2% | 44.7% | 63.2% |
| Kiwi | 7.9% | 26.3% | 42.1% | 52.6% |

## 복합 근거 질문

| 질문 | 토크나이저 | All@5 | All@10 | Coverage@5 | Coverage@10 |
|---|---|---:|---:|---:|---:|
| R-002 | Simple | 0.0% | 0.0% | 50.0% | 50.0% |
| R-024 | Simple | 0.0% | 0.0% | 0.0% | 0.0% |
| R-036 | Simple | 0.0% | 0.0% | 0.0% | 50.0% |
| R-002 | Kiwi | 0.0% | 100.0% | 50.0% | 100.0% |
| R-024 | Kiwi | 0.0% | 0.0% | 0.0% | 0.0% |
| R-036 | Kiwi | 0.0% | 0.0% | 0.0% | 0.0% |

## 검색 시간

| 토크나이저 | 평균 ms | p50 ms | p95 ms |
|---|---:|---:|---:|
| Simple | 68.98 | 65.73 | 86.64 |
| Kiwi | 55.34 | 42.70 | 58.73 |

## 직접 근거 실패 질의

| ID | 토크나이저 | 범주 | 첫 직접 근거 순위 | 원인 |
|---|---|---|---:|---|
| R-006 | Simple | pension_system | 8 | title_section_weight (직접 근거가 Top-5 밖) |
| R-008 | Simple | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-010 | Simple | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-011 | Simple | tax | 7 | title_section_weight (직접 근거가 Top-5 밖) |
| R-012 | Simple | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-014 | Simple | account_management | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-017 | Simple | account_management | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-018 | Simple | payout_withdrawal | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-019 | Simple | payout_withdrawal | 7 | title_section_weight (직접 근거가 Top-5 밖) |
| R-020 | Simple | payout_withdrawal | 6 | title_section_weight (직접 근거가 Top-5 밖) |
| R-022 | Simple | payout_withdrawal | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-023 | Simple | product_search | 6 | title_section_weight (직접 근거가 Top-5 밖) |
| R-024 | Simple | product_search | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-028 | Simple | product_search | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-032 | Simple | product_risk_fee | 6 | title_section_weight (직접 근거가 Top-5 밖) |
| R-033 | Simple | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-034 | Simple | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-035 | Simple | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-036 | Simple | product_code | 6 | title_section_weight (직접 근거가 Top-5 밖) |
| R-037 | Simple | paraphrase | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-038 | Simple | paraphrase | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-005 | Kiwi | pension_system | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-007 | Kiwi | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-008 | Kiwi | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-010 | Kiwi | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-011 | Kiwi | tax | 8 | title_section_weight (직접 근거가 Top-5 밖) |
| R-012 | Kiwi | tax | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-014 | Kiwi | account_management | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-015 | Kiwi | account_management | 10 | title_section_weight (직접 근거가 Top-5 밖) |
| R-017 | Kiwi | account_management | 6 | title_section_weight (직접 근거가 Top-5 밖) |
| R-018 | Kiwi | payout_withdrawal | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-022 | Kiwi | payout_withdrawal | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-024 | Kiwi | product_search | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-026 | Kiwi | product_search | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-028 | Kiwi | product_search | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-030 | Kiwi | product_risk_fee | 8 | title_section_weight (직접 근거가 Top-5 밖) |
| R-032 | Kiwi | product_risk_fee | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-033 | Kiwi | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-034 | Kiwi | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-035 | Kiwi | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-036 | Kiwi | product_code | >10 | repetitive_document_noise (상품 문서 내 비관련 요소 우선) |
| R-037 | Kiwi | paraphrase | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
| R-038 | Kiwi | paraphrase | >10 | query_document_vocabulary_gap (질의 표현과 근거 어휘 차이) |
