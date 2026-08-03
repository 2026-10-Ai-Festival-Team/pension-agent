# BM25-003 이후 실패 원인 재진단

## 비교 범위

`pension-v1` Simple BM25로 R-006, R-011, R-019, R-023을 원본 Corpus와 재분할 후보 Corpus에서 비교했다. 재분할 후보의 gold는 `element_ids` 후보를 원문으로 수동 확인해 이전했다. test 검색 결과는 사용하지 않았다.

| 질문 | 기존 순위 | 재분할 순위 | 기존 공통 토큰 | 재분할 공통 토큰 | 기존 Top-1 점수 | 재분할 Top-1 점수 | 재분류 |
|---|---:|---:|---:|---:|---:|---:|---|
| R-006 | 8 | >10 | 8 | 8 | 54.622 | 64.034 | `repetitive_document_noise` |
| R-011 | 7 | >10 | 6 | 3 | 36.225 | 32.753 | `query_document_vocabulary_gap` |
| R-019 | 7 | >10 | 5 | 5 | 41.698 | 50.541 | `repetitive_document_noise` |
| R-023 | 6 | >10 | 8 | 4 | 35.578 | 46.227 | `query_document_vocabulary_gap` |

## 관찰

- R-006과 R-019는 gold의 질의 공통 토큰 수가 유지됐는데도 경쟁 청크의 최고 점수가 커졌다. 청크 길이가 주원인이 아니라 반복되는 제도 용어를 가진 경쟁 문서가 우선하는 문제다.
- R-011과 R-023은 재분할 후 gold의 공통 토큰 수가 줄었다. 필요한 문맥을 분리해 BM25의 어휘 신호가 약해진 사례다.
- R-023은 Top-10 중 동일 source 비율이 2/10에서 5/10으로 증가했다. 다만 네 사례 전체에 source diversity를 바로 적용할 근거로는 부족하다.

## 결정

**Rejected**

- Corpus 청크: 23,421 → 23,503
- Dev Direct R@5: 63.3% → 43.3%
- Dev Direct R@10: 80.0% → 53.3%
- MRR: 0.401 → 0.211
- 목표 실패 개선: 0개
- 운영 Corpus와 평가셋 gold는 원상 복구했다.

다음 실험은 청킹이 아니라 dev 실패 전체에서 `repetitive_document_noise`와 `query_document_vocabulary_gap`의 빈도를 재분석한 뒤 하나만 선택한다.
