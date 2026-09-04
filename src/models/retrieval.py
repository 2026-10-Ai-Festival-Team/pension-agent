from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.models.chunk import ChunkLocator
from src.models.document import AuthorityLevel, SourceType
class SearchResult(BaseModel):
    rank: int = Field(ge=1); chunk_id: str; score: float; text: str; source_id: str; source_path: str; source_format: str; document_type: str
    title: Optional[str] = None; section: Optional[str] = None; locator: ChunkLocator
    source_type: SourceType = SourceType.ORIGINAL
    authority_level: AuthorityLevel = AuthorityLevel.PRIMARY
    as_of_date: Optional[str] = None
    product_codes: List[str] = Field(default_factory=list); element_ids: List[str] = Field(default_factory=list); metadata: Dict[str, Any] = Field(default_factory=dict)
class SearchResponse(BaseModel):
    query: str; tokenizer: str; total_candidates: int; results: List[SearchResult]
