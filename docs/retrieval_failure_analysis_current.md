# 현재 BM25 dev 실패 재분석

- 기준: 원본 Corpus 23,421청크, Simple, `pension-v1`
- test 질문과 결과는 사용하지 않았다.

## 실패 분포

| Failure type | Top-5 실패·Top-10 성공 | Direct Top-10 실패 |
|---|---:|---:|
| `repetitive_document_noise` | 0 | 1 |
| `query_document_vocabulary_gap` | 0 | 1 |
| `table_row_term_missing` | 3 | 2 |
| `gold_competitor_mismatch` | 2 | 2 |
| `other` | 0 | 0 |

## Source cap 시뮬레이션

Top-100을 점수 순서로 유지한 뒤 source별 반환 수만 제한했다. 이는 검색 코드 변경이 아닌 오프라인 가정이다.

| Variant | Dev R@5 | Dev R@10 | Improved | Regressed |
|---|---:|---:|---:|---:|
| No cap | 19/30 | 24/30 | 0 | 0 |
| Max 3/source | 18/30 | 22/30 | 1 | 3 |
| Max 2/source | 17/30 | 21/30 | 1 | 5 |

상세 토큰·source 점유·질문별 cap 순위는 Git 제외 CSV에 저장했다.
