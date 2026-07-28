# Representative Parse Quality Report

## Coverage

- Diagnosed representative documents: 12
- OCR-required candidates: 3
- Table-bearing candidates: 5

## Recommended parser trials

- `openpyxl`: 2
- `pymupdf`: 7
- `python-docx`: 2
- `python-pptx`: 1

## Documents needing extra attention

- `docs_renamed/doc47.pdf`: table candidates detected: 1
- `docs_renamed/doc30.pdf`: pages with no native text: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
- `docs_renamed/doc37.pdf`: pages with no native text: [1, 2, 3, 4, 5, 6, 7, 8]
- `docs_renamed/doc31.pdf`: pages with no native text: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
- `docs_renamed/doc35.docx`: DOCX has no stable rendered page positions without a rendering step
- `docs_renamed/doc41.docx`: DOCX has no stable rendered page positions without a rendering step
- `docs_renamed/doc33.pptx`: Text-box reading order requires visual spot-checking
- `docs_renamed/doc34.xlsx`: merged-cell ranges: 1
- `docs_renamed/doc29.xlsx`: merged-cell ranges: 11
- `투자설명서/KR510902511M/R2_KR510902511M.pdf`: table candidates detected: 131
- `투자설명서/KR510902773M/R2_KR510902773M.pdf`: table candidates detected: 125
