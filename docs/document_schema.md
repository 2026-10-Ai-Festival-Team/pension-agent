# Document Schema v1

## Purpose

Convert company-provided PDF, DOCX, PPTX, and XLSX files into a common structure while preserving source locations for evidence display.

## Principles

1. Source files are never modified.
2. Extraction order and source locations are preserved.
3. Parsers do not summarize or interpret content.
4. All date candidates are retained; `effective_date` is empty unless explicit.
5. A parser never invents unavailable page numbers.
6. Tables remain structured separately from plain text.

## Location rules

| Format | Locator fields |
| --- | --- |
| PDF | `page`, `bbox`, `block_index` |
| DOCX | `block_index` |
| PPTX | `slide`, `bbox`, `block_index` |
| XLSX | `sheet`, `cell_range` |

## Elements

`title`, `heading`, `paragraph`, `table`, `image`, and `other` are represented by `DocumentElement`. Tables use `TableData`; all other elements require non-empty text.

## Known limitations

- PDF reading order may differ from visual order, and table text can duplicate text blocks.
- DOCX does not offer stable rendered page locations without a rendering step.
- PPTX grouped shapes and SmartArt can be partially unavailable.
- XLSX formula values depend on the last value stored by the workbook.
