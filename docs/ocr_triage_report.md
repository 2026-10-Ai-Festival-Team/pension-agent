# OCR Triage Report

## Scope and rule

- PDFs inspected: 137
- Native-text-absent pages: 105
- OCR candidates: 53
- Rule: native text is absent, embedded-image coverage is at least 35%, and the page is not a likely first-page cover.
- `no_native_text_without_embedded_image` remains a manual-review item; it may be blank, vector-only, or a scanned page embedded in an unsupported form.

## Classification reasons

| Reason | Pages |
|---|---:|
| likely_cover_page | 2 |
| manual_verified_content | 2 |
| no_native_text_high_image_coverage | 51 |
| no_native_text_low_image_coverage | 48 |
| no_native_text_without_embedded_image | 2 |

## Native-text-empty documents

| Relative path | Pages | OCR-candidate pages |
|---|---:|---:|
| `docs_renamed/doc31.pdf` | 11 | 11 |
| `docs_renamed/doc37.pdf` | 8 | 8 |
| `docs_renamed/doc56.pdf` | 2 | 2 |

## Manual visual inspection

- `docs_renamed/doc31.pdf`: 전 11페이지에 내용이 있는 이미지 기반 안내·표 레이아웃을 확인함.
- `docs_renamed/doc37.pdf`: 전 8페이지에 내용이 있는 이미지 기반 가이드·표·그래프 레이아웃을 확인함.
- `docs_renamed/doc56.pdf`: 전 2페이지에 내용이 있는 렌더링 텍스트·표를 확인했으며, 이미지 객체가 없어 자동 규칙에서는 누락됨.

## Documents with OCR candidates

- `docs_renamed/doc30.pdf`: pages 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
- `docs_renamed/doc31.pdf`: pages 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
- `docs_renamed/doc37.pdf`: pages 1, 2, 3, 4, 5, 6, 7, 8
- `docs_renamed/doc54.pdf`: pages 8, 16
- `docs_renamed/doc56.pdf`: pages 1, 2
- `docs_renamed/doc7.pdf`: pages 5, 6, 8, 11, 14, 20
- `docs_renamed/doc9.pdf`: pages 4
- `투자설명서/KR5120420091/R2_KR5120420091.pdf`: pages 55, 56
- `투자설명서/KR5120450015/R2_KR5120450015.pdf`: pages 62, 63, 64
- `투자설명서/KR5120450018/R2_KR5120450018.pdf`: pages 62, 63, 64

## Next action

Use the OCR-candidate list as the review queue. Select an OCR engine only after spot-checking a small sample from each candidate group.
