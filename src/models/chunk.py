"""Search-oriented chunks with source and locator traceability."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from src.models.document import AuthorityLevel, SourceType


class ChunkType(str, Enum):
    PARAGRAPH_GROUP = "paragraph_group"
    QA = "qa"
    TABLE = "table"
    SLIDE = "slide"
    SPREADSHEET_ROWS = "spreadsheet_rows"


class ChunkLocator(BaseModel):
    """Source position spanning one or more elements in a search chunk."""

    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    slide_start: Optional[int] = Field(default=None, ge=1)
    slide_end: Optional[int] = Field(default=None, ge=1)
    sheet: Optional[str] = None
    cell_range: Optional[str] = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "ChunkLocator":
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_start > self.page_end
        ):
            raise ValueError("page_start must not be after page_end")
        if (
            self.slide_start is not None
            and self.slide_end is not None
            and self.slide_start > self.slide_end
        ):
            raise ValueError("slide_start must not be after slide_end")
        return self


class SearchChunk(BaseModel):
    """A retrieval unit derived without summarizing its source content."""

    schema_version: str = "1.0"
    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_format: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    source_type: SourceType = SourceType.ORIGINAL
    authority_level: AuthorityLevel = AuthorityLevel.PRIMARY
    as_of_date: Optional[str] = None
    title: Optional[str] = None
    section: Optional[str] = None
    chunk_type: ChunkType
    text: str = Field(min_length=1)
    locator: ChunkLocator
    product_codes: List[str] = Field(default_factory=list)
    date_candidates: List[str] = Field(default_factory=list)
    element_ids: List[str] = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_element_ids(self) -> "SearchChunk":
        if len(self.element_ids) != len(set(self.element_ids)):
            raise ValueError("element_ids must not contain duplicates")
        return self
