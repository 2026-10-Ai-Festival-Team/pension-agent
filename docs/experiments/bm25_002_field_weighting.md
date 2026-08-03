# BM25-002: 제목·섹션 필드 가중치 — 보류

## 채택 기준선

- 토크나이저: Simple
- 질의 정규화: `pension-v1`
- Corpus와 BM25 저장 인덱스: 변경 없음
- 평가 범위: dev만 사용

## 사전 진단 결과

`pension-v1` 적용 후 남은 12개 dev 분석 대상에서 다음을 확인했다.

- Direct Top-5 실패: 11개
- Direct Top-10 실패: 6개
- 제목·섹션 신호 후보: 0개

제목·섹션 신호 후보는 정규화된 질의 토큰이 정답 청크의 제목 또는 섹션에는 중첩되고, 본문 중첩은 없거나 낮은 경우로 정의했다. 이 조건을 만족하는 질문이 없으므로 제목·섹션 점수를 추가할 근거가 부족하다.

## 결정

**보류**. 필드 인덱스와 가중치 격자를 구현하거나 평가하지 않는다. 현재 실패를 제목·섹션 가중치로 해결하려 하면 일반 제목·목차 청크를 과대평가할 위험이 있다.

정규화 후 주된 원인은 `chunk_too_broad` 4개, `query_document_vocabulary_gap` 3개, `table_rendering` 2개, `repetitive_document_noise` 2개, `evidence_spans_multiple_chunks` 1개다. 다음 실험은 가장 많은 `chunk_too_broad`를 대상으로 한 인접 청크 확장 또는 청크 경계 개선으로 진행한다.

상세 토큰·중첩·Top-10은 [정규화 후 실패 분석](../retrieval_failure_analysis_normalized.md)과 Git 제외 진단 CSV에서 확인할 수 있다.
