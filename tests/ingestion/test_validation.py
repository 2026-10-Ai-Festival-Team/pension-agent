from src.ingestion.validation import validate_parsed_document
from src.models.document import (
    DocumentElement,
    DocumentType,
    ElementType,
    Locator,
    ParsedDocument,
    SourceFormat,
    TableData,
)


def make_document() -> ParsedDocument:
    return ParsedDocument(
        source_id="source-1",
        relative_path="docs/sample.pdf",
        filename="sample.pdf",
        source_format=SourceFormat.PDF,
        document_type=DocumentType.PENSION_GUIDE,
        elements=[
            DocumentElement(
                element_id="source-1-p1-b0",
                order=0,
                kind=ElementType.PARAGRAPH,
                text="본문",
                locator=Locator(page=1, block_index=0),
            ),
            DocumentElement(
                element_id="source-1-p1-t0",
                order=1,
                kind=ElementType.TABLE,
                table=TableData(rows=[["항목"]]),
                locator=Locator(page=1, block_index=1),
            ),
        ],
    )


def test_validation_accepts_valid_document() -> None:
    assert validate_parsed_document(make_document()) == []


def test_validation_reports_extension_and_order_errors() -> None:
    document = make_document().model_copy(
        update={"relative_path": "docs/sample.docx"}
    )
    document.elements[1].order = 3

    errors = validate_parsed_document(document)

    assert any("source_format extension mismatch" in error for error in errors)
    assert any("non-contiguous order" in error for error in errors)


def test_validation_reports_format_specific_locator_errors() -> None:
    document = make_document()
    document.elements[0].locator = Locator(slide=1)

    errors = validate_parsed_document(document)

    assert "PDF page missing: source-1-p1-b0" in errors
    assert "PDF has unexpected slide: source-1-p1-b0" in errors
