# OCR 분류 보고서

## 범위와 규칙

- 검사한 PDF: 137개
- 네이티브 텍스트가 없는 페이지: 105개
- OCR 후보: 53개
- 규칙: 네이티브 텍스트가 없고, 임베디드 이미지 면적 비율이 최소 35%이며, 첫 페이지 표지로 보이지 않는 경우다.
- `no_native_text_without_embedded_image`는 수동 검토 대상으로 남긴다. 빈 페이지, 벡터 전용 페이지, 지원하지 않는 형태로 삽입된 스캔 페이지일 수 있다.

## 분류 사유

| 사유 | 페이지 수 |
|---|---:|
| likely_cover_page | 2 |
| manual_verified_content | 2 |
| no_native_text_high_image_coverage | 51 |
| no_native_text_low_image_coverage | 48 |
| no_native_text_without_embedded_image | 2 |

## 네이티브 텍스트가 없는 문서

| 상대 경로 | 페이지 수 | OCR 후보 페이지 수 |
|---|---:|---:|
| `docs_renamed/doc31.pdf` | 11 | 11 |
| `docs_renamed/doc37.pdf` | 8 | 8 |
| `docs_renamed/doc56.pdf` | 2 | 2 |

## 수동 시각 점검

- `docs_renamed/doc31.pdf`: 전 11페이지에 내용이 있는 이미지 기반 안내·표 레이아웃을 확인함.
- `docs_renamed/doc37.pdf`: 전 8페이지에 내용이 있는 이미지 기반 가이드·표·그래프 레이아웃을 확인함.
- `docs_renamed/doc56.pdf`: 전 2페이지에 내용이 있는 렌더링 텍스트·표를 확인했으며, 이미지 객체가 없어 자동 규칙에서는 누락됨.

## OCR 후보가 있는 문서

- `docs_renamed/doc30.pdf`: 페이지 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
- `docs_renamed/doc31.pdf`: 페이지 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
- `docs_renamed/doc37.pdf`: 페이지 1, 2, 3, 4, 5, 6, 7, 8
- `docs_renamed/doc54.pdf`: 페이지 8, 16
- `docs_renamed/doc56.pdf`: 페이지 1, 2
- `docs_renamed/doc7.pdf`: 페이지 5, 6, 8, 11, 14, 20
- `docs_renamed/doc9.pdf`: 페이지 4
- `투자설명서/KR5120420091/R2_KR5120420091.pdf`: 페이지 55, 56
- `투자설명서/KR5120450015/R2_KR5120450015.pdf`: 페이지 62, 63, 64
- `투자설명서/KR5120450018/R2_KR5120450018.pdf`: 페이지 62, 63, 64

## 다음 작업

OCR 후보 목록을 검토 대기열로 사용한다. 각 후보 그룹에서 작은 표본을 점검한 뒤에만 OCR 엔진을 선택한다.
