from src.models.document import DocumentElement, DocumentType, ElementType, Locator, ParsedDocument, SourceFormat, TableData
from src.preprocessing.config import ChunkingConfig
from src.preprocessing.paragraph_chunker import ParagraphChunker
from src.preprocessing.table_chunker import TableChunker
from src.preprocessing.spreadsheet_chunker import SpreadsheetChunker
from src.preprocessing.corpus_builder import CorpusBuilder
from src.ingestion.registry import build_default_registry


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


def test_heading_before_table_is_included_in_table_chunk():
    heading = DocumentElement(element_id="heading", order=0, kind=ElementType.HEADING, text="위험등급", locator=Locator(page=1))
    table = DocumentElement(element_id="table", order=1, kind=ElementType.TABLE, table=TableData(rows=[["등급"], ["3"]]), locator=Locator(page=1))
    chunks = CorpusBuilder(build_default_registry())._build_ordered_document(document([heading, table]))
    assert len(chunks) == 1
    assert chunks[0].text.startswith("위험등급\n등급")
    assert chunks[0].element_ids == ["heading", "table"]


def test_pdf_question_topic_starts_new_paragraph_chunk():
    elements = [
        DocumentElement(element_id="a", order=0, kind=ElementType.PARAGRAPH, text="○ 첫 질문\n첫 답변", locator=Locator(page=1)),
        DocumentElement(element_id="b", order=1, kind=ElementType.PARAGRAPH, text="○ 둘째 질문\n둘째 답변", locator=Locator(page=1)),
    ]

    chunks = ParagraphChunker(ChunkingConfig()).chunk_elements(document(elements), elements)

    assert [chunk.element_ids for chunk in chunks] == [["a"], ["b"]]


def test_short_single_topic_pdf_paragraph_is_not_split():
    elements = [
        DocumentElement(element_id="a", order=0, kind=ElementType.PARAGRAPH, text="설명 첫 부분", locator=Locator(page=1)),
        DocumentElement(element_id="b", order=1, kind=ElementType.PARAGRAPH, text="설명 둘째 부분", locator=Locator(page=1)),
    ]

    chunks = ParagraphChunker(ChunkingConfig()).chunk_elements(document(elements), elements)

    assert len(chunks) == 1


def test_wide_table_is_split_into_two_row_groups_with_context():
    rows = [["구분", "설명"]] + [[f"항목 {index}", "충분히 긴 설명" * 10] for index in range(5)]
    element = DocumentElement(element_id="table", order=0, kind=ElementType.TABLE, table=TableData(rows=rows), locator=Locator(page=1))
    doc = document([element]).model_copy(update={"title": "퇴직연금 과세 비교"})

    chunks = TableChunker(ChunkingConfig()).chunk_element(doc, element)

    assert len(chunks) == 3
    assert all(chunk.text.startswith("퇴직연금 과세 비교\n구분 | 설명") for chunk in chunks)
    assert [chunk.metadata["data_row_start"] for chunk in chunks] == [2, 4, 6]
