"""Versioned, source-location-preserving document schema."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator


class SourceFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"


class DocumentType(str, Enum):
    PENSION_GUIDE = "pension_guide"
    INVESTMENT_PRODUCT = "investment_product"
    UNKNOWN = "unknown"


class SourceType(str, Enum):
    """원천 데이터와 검색 보강 데이터를 구분한다."""

    ORIGINAL = "original"
    AUGMENTED = "augmented"


class AuthorityLevel(str, Enum):
    """금융 사실을 확정할 때의 근거 권위를 표시한다."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class ElementType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    IMAGE = "image"
    OTHER = "other"


class Locator(BaseModel):
    """Original location of an element, using fields appropriate to its format."""

    page: Optional[int] = Field(default=None, ge=1)
    slide: Optional[int] = Field(default=None, ge=1)
    sheet: Optional[str] = None
    cell_range: Optional[str] = None
    block_index: Optional[int] = Field(default=None, ge=0)
    bbox: Optional[Tuple[float, float, float, float]] = None


class TableData(BaseModel):
    rows: List[List[Optional[str]]] = Field(default_factory=list)
    merged_ranges: List[str] = Field(default_factory=list)


class DocumentElement(BaseModel):
    element_id: str
    order: int = Field(ge=0)
    kind: ElementType
    locator: Locator
    text: Optional[str] = None
    table: Optional[TableData] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_content(self) -> "DocumentElement":
        if self.kind == ElementType.TABLE and self.table is None:
            raise ValueError("TABLE 요소에는 table 데이터가 필요합니다.")
        if self.kind != ElementType.TABLE and not self.text:
            raise ValueError("비표 요소에는 text가 필요합니다.")
        return self


class ParsedDocument(BaseModel):
    schema_version: str = "1.0"
    source_id: str
    relative_path: str
    filename: str
    source_format: SourceFormat
    document_type: DocumentType
    source_type: SourceType = SourceType.ORIGINAL
    authority_level: AuthorityLevel = AuthorityLevel.PRIMARY
    # 원문에 명시된 기준일이 있다면 effective_date와 같은 값으로 보존한다.
    as_of_date: Optional[str] = None
    title: Optional[str] = None
    product_codes: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    date_candidates: List[str] = Field(default_factory=list)
    elements: List[DocumentElement] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
