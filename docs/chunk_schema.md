# Search Chunk Schema v1

## 목적

`ParsedDocument`의 요소를 검색 가능한 단위로 변환하면서 원문 문서와 위치를
역추적할 수 있게 한다. 청크 생성은 원문을 요약하거나 새 정보를 생성하지 않는다.

## 핵심 필드

| Field | Purpose |
|---|---|
| `source_id` | 원본 `ParsedDocument`를 식별한다. |
| `locator` | 페이지·슬라이드·시트·셀 범위를 보존한다. |
| `element_ids` | 청크를 만든 원본 요소를 역추적한다. |
| `text` | 검색 인덱스에 넣는 원문 기반 텍스트다. |

## 원칙

1. 모든 청크는 하나의 `source_id`에만 속한다.
2. `element_ids`는 하나 이상이어야 하며 중복될 수 없다.
3. PDF 청크는 `page_start`와 `page_end`를 보존한다. 초기 구현에서는 페이지를 넘지 않는다.
4. PPTX 청크는 `slide_start`와 `slide_end`를 보존한다.
5. XLSX 청크는 `sheet`와 `cell_range`를 보존한다.
6. 상품 문서는 `product_codes`를 각 청크에 상속한다.
7. 표 청크는 각 행 묶음마다 헤더를 반복한다.
8. 빈 `text` 청크는 생성하지 않는다.
9. 청크 생성 과정에서 원문을 요약하거나 새 정보를 추가하지 않는다.
10. OCR 대상 페이지는 OCR 완료 전까지 기존 네이티브 파싱 결과와 별도 상태로 유지한다.

## Chunk types

| Type | Use |
|---|---|
| `paragraph_group` | PDF·DOCX의 연속 문단 또는 설명형 XLSX 시트 |
| `qa` | 질문과 답변이 하나의 구조 단위인 경우 |
| `table` | PDF·DOCX 표의 헤더와 행 묶음 |
| `slide` | PPTX 슬라이드 또는 큰 슬라이드의 요소 그룹 |
| `spreadsheet_rows` | XLSX의 헤더와 행 묶음 |

## Locator conventions

- `page_start`/`page_end`, `slide_start`/`slide_end`은 포함 범위이며 시작값이 끝값보다 클 수 없다.
- PDF·DOCX 문단, PDF·DOCX 표는 각 원소의 원래 `element_id`를 유지한다.
- PDF는 `page_start == page_end`를 기본으로 둔다.
- DOCX는 안정적인 렌더링 페이지가 없으므로 locator의 페이지 필드를 비워 두고 `element_ids`로 본문 블록을 추적한다.
- XLSX는 `sheet`와 `cell_range`를 반드시 설정한다.

## Example

```json
{
  "chunk_id": "df858a02af69f9fb-p2-c1",
  "source_id": "df858a02af69f9fb",
  "source_path": "docs_renamed/doc1.pdf",
  "source_format": "pdf",
  "document_type": "pension_guide",
  "title": "퇴직연금 안내",
  "section": null,
  "chunk_type": "paragraph_group",
  "text": "검색에 사용할 원문 기반 본문",
  "locator": {
    "page_start": 2,
    "page_end": 2,
    "slide_start": null,
    "slide_end": null,
    "sheet": null,
    "cell_range": null
  },
  "product_codes": [],
  "date_candidates": [],
  "element_ids": ["df858a02af69f9fb-p2-b3"],
  "metadata": {}
}
```
