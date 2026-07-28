# 대표 문서 파싱 품질 보고서

## 범위

- 진단한 대표 문서: 12개
- OCR 필요 후보: 3개
- 표 포함 후보: 5개

## 권장 파서 시험

- `openpyxl`: 2
- `pymupdf`: 7
- `python-docx`: 2
- `python-pptx`: 1

## 추가 검토가 필요한 문서

- `docs_renamed/doc47.pdf`: 표 후보 감지: 1
- `docs_renamed/doc30.pdf`: 네이티브 텍스트가 없는 페이지: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
- `docs_renamed/doc37.pdf`: 네이티브 텍스트가 없는 페이지: [1, 2, 3, 4, 5, 6, 7, 8]
- `docs_renamed/doc31.pdf`: 네이티브 텍스트가 없는 페이지: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
- `docs_renamed/doc35.docx`: 렌더링 단계 없이는 안정적인 DOCX 페이지 위치를 얻을 수 없음
- `docs_renamed/doc41.docx`: 렌더링 단계 없이는 안정적인 DOCX 페이지 위치를 얻을 수 없음
- `docs_renamed/doc33.pptx`: 텍스트 상자 읽기 순서는 시각 점검이 필요함
- `docs_renamed/doc34.xlsx`: 병합 셀 범위: 1
- `docs_renamed/doc29.xlsx`: 병합 셀 범위: 11
- `투자설명서/KR510902511M/R2_KR510902511M.pdf`: 표 후보 감지: 131
- `투자설명서/KR510902773M/R2_KR510902773M.pdf`: 표 후보 감지: 125
