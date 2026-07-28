# 검색 평가 질문 스키마

`evaluation/retrieval_questions.jsonl`은 한 줄에 하나의 질문을 저장한다. 이 파일은 검색 품질만 평가하기 위한 내부 데이터이며, 질문의 답변을 생성하지 않는다.

## 질문 필드

| 필드 | 설명 |
|---|---|
| `question_id` | 고정된 고유 질문 ID (`R-001` 등) |
| `split` | 규칙 개선에 사용하는 `dev` 또는 최종 확인용 `test` |
| `question` | 사용자 질의 문장 |
| `category` | 제도·세제·상품 등 분석 범주 |
| `answerable` | 제공 Corpus만으로 근거 기반 답변이 가능한지 여부 |
| `requires_ocr` | 정답 근거에 OCR 처리가 필요한지 여부 |
| `product_codes` | 직접 검색하는 상품코드 목록 |
| `relevant_chunks` | 확정된 정답 청크 목록 |
| `relevant_source_ids` | 확정된 정답 문서 ID 목록 |
| `required_terms` | 답변 근거에 반드시 포함되어야 하는 용어 목록 |
| `notes` | 라벨링 상태와 예외 사유 |

## 초기 초안과 라벨링

초안 단계에서는 `relevant_chunks`, `relevant_source_ids`, `required_terms`를 빈 배열로 유지하고 `notes`에 `pending_label`을 둔다. 검색 결과 점수나 순위는 관련도 판정 근거가 아니다.

후보 검토가 끝나면 답변 가능한 질문에는 다음 구조의 직접·보조 근거만 기록한다.

```json
{
  "chunk_id": "source-paragraph_group-abc",
  "source_id": "source",
  "relevance": 2,
  "locator": {"page_start": 3, "page_end": 3}
}
```

관련도는 `2`가 그 청크만으로 직접 답할 수 있는 근거, `1`이 필요한 보조 근거다. 답변 불가능 질문은 `answerable=false`, 빈 근거 배열, 그리고 `unsupported_question:` 사유를 유지한다.

## 편향을 줄이는 라벨링 순서

1. 같은 Corpus SHA-256과 BM25 파라미터로 Simple·Kiwi Top-20을 수집한다.
2. 두 결과의 합집합에서 원문·출처 위치만 보고 관련도를 판정한다.
3. 근거가 없으면 Top-100 재검색, 핵심 용어 Corpus 검색, 관련 문서 전체 청크, 원본 문서 위치 순으로 추가 확인한다.
4. 결과를 `retrieval_failure`, `corpus_missing`, `unsupported_question`, `gold_label_error` 중 하나로 기록한다.

라벨링을 완료하면 `pending_label`을 제거하고, 각 `chunk_id`·`source_id`·`locator`가 현재 Corpus와 일치하는지 검증한다. OCR 의존 질문은 기본 BM25 지표와 분리해 집계한다.

## 재현성

후보 수집 결과에는 Corpus SHA-256, 토크나이저 이름, 두 검색기의 순위와 점수를 함께 저장한다. 평가셋을 동결할 때는 별도 메타데이터에 데이터셋 버전, Corpus SHA-256, 라벨링 방법(`simple_kiwi_top20_union_plus_manual_fallback`)을 기록한다.
