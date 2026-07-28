from src.models.document import DocumentElement, DocumentType, ElementType, Locator, ParsedDocument, SourceFormat, TableData
from src.preprocessing.config import ChunkingConfig
from src.preprocessing.paragraph_chunker import ParagraphChunker
from src.preprocessing.table_chunker import TableChunker
from src.preprocessing.spreadsheet_chunker import SpreadsheetChunker


def document(elements):
    return ParsedDocument(source_id="s", relative_path="x.pdf", filename="x.pdf", source_format=SourceFormat.PDF, document_type=DocumentType.INVESTMENT_PRODUCT, product_codes=["KR5123490017"], elements=elements)


def test_pdf_paragraph_chunks_do_not_cross_pages():
    doc = document([DocumentElement(element_id="a", order=0, kind=ElementType.PARAGRAPH, text="첫 페이지", locator=Locator(page=1)), DocumentElement(element_id="b", order=1, kind=ElementType.PARAGRAPH, text="둘째 페이지", locator=Locator(page=2))])
    chunks = ParagraphChunker(ChunkingConfig()).chunk_elements(doc, doc.elements)
    assert [chunk.locator.page_start for chunk in chunks] == [1, 2]


def test_table_chunks_repeat_header_and_product_code():
    rows = [["구분", "값"]] + [[str(index), "x"] for index in range(25)]
    element = DocumentElement(element_id="table", order=0, kind=ElementType.TABLE, table=TableData(rows=rows), locator=Locator(page=1))
    chunks = TableChunker(ChunkingConfig(table_rows_per_chunk=20)).chunk_element(document([element]), element)
    assert len(chunks) == 2
    assert all(chunk.text.startswith("구분 | 값") for chunk in chunks)
    assert all(chunk.product_codes == ["KR5123490017"] for chunk in chunks)


def test_spreadsheet_chunks_repeat_header_and_split_locator_rows():
    rows = [["상품", "수익률"]] + [[str(index), "1%"] for index in range(25)]
    element = DocumentElement(element_id="sheet", order=0, kind=ElementType.TABLE, table=TableData(rows=rows), locator=Locator(sheet="상품", cell_range="A1:B26"))
    workbook = ParsedDocument(source_id="sheet-source", relative_path="x.xlsx", filename="x.xlsx", source_format=SourceFormat.XLSX, document_type=DocumentType.INVESTMENT_PRODUCT, product_codes=["KR5123490017"], elements=[element])
    chunks = SpreadsheetChunker(ChunkingConfig(spreadsheet_rows_per_chunk=20)).chunk(workbook)
    assert [chunk.locator.cell_range for chunk in chunks] == ["A2:B21", "A22:B26"]
    assert all(chunk.text.startswith("상품 | 수익률") for chunk in chunks)
