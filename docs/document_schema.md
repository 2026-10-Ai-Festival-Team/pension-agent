# 문서 스키마 v1

## 목적

사측 제공 PDF·DOCX·PPTX·XLSX 파일을 공통 구조로 변환하면서, 근거 표시를 위한 원문 위치를 보존한다.

## 원칙

1. 원본 파일은 수정하지 않는다.
2. 추출 순서와 원문 위치를 보존한다.
3. 파서는 내용을 요약하거나 해석하지 않는다.
4. 날짜 후보는 모두 보존하며, 명시적 근거가 없으면 `effective_date`는 비운다.
5. 파서는 존재하지 않는 페이지 번호를 만들지 않는다.
6. 표는 일반 텍스트와 분리된 구조로 보존한다.

## 위치 규칙

| 형식 | Locator 필드 |
| --- | --- |
| PDF | `page`, `bbox`, `block_index` |
| DOCX | `block_index` |
| PPTX | `slide`, `bbox`, `block_index` |
| XLSX | `sheet`, `cell_range` |

## 요소

`title`, `heading`, `paragraph`, `table`, `image`, `other`는 `DocumentElement`로 표현한다. 표는 `TableData`를 사용하고, 다른 요소에는 비어 있지 않은 텍스트가 필요하다.

## 알려진 제약

- PDF 읽기 순서는 화면 순서와 다를 수 있으며, 표 텍스트가 일반 텍스트 블록과 중복될 수 있다.
- DOCX는 렌더링 단계 없이는 안정적인 페이지 위치를 제공하지 않는다.
- PPTX 그룹 도형과 SmartArt는 일부 추출하지 못할 수 있다.
- XLSX 수식 값은 통합 문서에 마지막으로 저장된 값에 따라 달라진다.

## PPTX 위치와 읽기 순서 규칙

- `locator.slide`는 1부터 시작하며, PPTX에는 PDF식 페이지 번호를 만들지 않는다.
- `locator.block_index`는 도형을 `(top, left, shape_id)` 순으로 정렬한 뒤의 위치다.
- `locator.bbox`는 EMU 단위의 `(left, top, right, bottom)`이며 `metadata.bbox_unit`에 단위를 기록한다.
- 그룹 도형 자체는 요소를 만들지 않는다. 하위 요소를 재귀 순회하며 `group_path`를 보존한다.

이 순서는 화면 기반 읽기 순서의 휴리스틱일 뿐, 작성자의 의도를 보장하지 않는다.

## PPTX 미지원 콘텐츠

최소 파서는 차트 데이터, SmartArt·미지원 그래픽 프레임, 이미지 OCR, 발표자 노트, 애니메이션, 도형 표시 순서를 추출하지 않고 경고로 기록한다.

## XLSX 위치와 값 규칙

- `locator.sheet`는 원래 워크시트 이름이며, `locator.cell_range`는 비어 있지 않은 최소 셀 범위다.
- `locator.block_index`는 통합 문서 순서 기준 0부터 시작한다. XLSX에는 페이지나 슬라이드 위치를 만들지 않는다.
- 비어 있지 않은 각 워크시트는 하나의 `TABLE` 요소가 된다. 병합 범위는 병합 셀을 채우지 않고 `TableData.merged_ranges`에 저장한다.
- 날짜와 시간은 ISO 문자열로 직렬화한다. 숫자·날짜 형식은 `metadata.formatted_cells`에 보존한다.
- 수식 셀은 저장된 계산값이 있으면 이를 사용하고, 없으면 수식 텍스트를 사용한다. 두 값은 `metadata.formula_cells`에 보존한다.

## XLSX 제약

파서는 수식을 계산하거나, 차트 데이터·이미지 OCR을 추출하거나, 매크로를 실행·해석하거나, 한 워크시트의 여러 독립 표를 분리하지 않는다.
