"""PyMuPDF parser that preserves page, block, and table coordinates."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from src.ingestion.common import (
    extract_date_candidates,
    extract_product_codes,
    make_source_id,
    normalize_text,
    relative_path,
)
from src.models.document import (
    DocumentElement,
    DocumentType,
    ElementType,
    Locator,
    ParsedDocument,
    SourceFormat,
    TableData,
)


class PdfParser:
    supported_extensions = {".pdf"}

    def parse(self, path: Path, source_root: Path) -> ParsedDocument:
        relative = relative_path(path, source_root)
        source_id = make_source_id(relative)
        elements: list[DocumentElement] = []
        warnings: list[str] = []
        full_text_parts: list[str] = []
        order = 0

        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                blocks = page.get_text("blocks", sort=True)
                text_element_count = 0

                for block_index, block in enumerate(blocks):
                    x0, y0, x1, y1 = map(float, block[:4])
                    text = normalize_text(str(block[4]))
                    if not text:
                        continue
                    elements.append(
                        DocumentElement(
                            element_id=f"{source_id}-p{page_number}-b{block_index}",
                            order=order,
                            kind=ElementType.PARAGRAPH,
                            text=text,
                            locator=Locator(
                                page=page_number,
                                block_index=block_index,
                                bbox=(x0, y0, x1, y1),
                            ),
                            metadata={"parser": "pymupdf", "native_block": True},
                        )
                    )
                    full_text_parts.append(text)
                    order += 1
                    text_element_count += 1

                if text_element_count == 0:
                    warnings.append(f"page {page_number}: usable native text block 없음")

                try:
                    for table_index, table in enumerate(page.find_tables().tables):
                        rows = [
                            [normalize_text(str(cell)) if cell is not None else None for cell in row]
                            for row in table.extract()
                        ]
                        elements.append(
                            DocumentElement(
                                element_id=f"{source_id}-p{page_number}-t{table_index}",
                                order=order,
                                kind=ElementType.TABLE,
                                table=TableData(rows=rows),
                                locator=Locator(
                                    page=page_number,
                                    block_index=table_index,
                                    bbox=tuple(float(value) for value in table.bbox),
                                ),
                                metadata={"parser": "pymupdf", "possible_text_duplication": True},
                            )
                        )
                        order += 1
                except Exception as exc:  # A table failure must not discard page text.
                    warnings.append(f"page {page_number}: table extraction 실패: {type(exc).__name__}")

        full_text = "\n".join(full_text_parts)
        document_type = (
            DocumentType.INVESTMENT_PRODUCT
            if "투자설명서" in relative
            else DocumentType.PENSION_GUIDE
        )
        return ParsedDocument(
            source_id=source_id,
            relative_path=relative,
            filename=path.name,
            source_format=SourceFormat.PDF,
            document_type=document_type,
            title=self._infer_title(elements),
            product_codes=extract_product_codes(relative, full_text),
            date_candidates=extract_date_candidates(full_text),
            elements=elements,
            warnings=warnings,
            metadata={"parser": "pymupdf", "element_count": len(elements)},
        )

    @staticmethod
    def _infer_title(elements: list[DocumentElement]) -> str | None:
        for element in elements:
            if element.locator.page != 1 or not element.text:
                continue
            first_line = element.text.splitlines()[0]
            if len(first_line) <= 150:
                return first_line
        return None
