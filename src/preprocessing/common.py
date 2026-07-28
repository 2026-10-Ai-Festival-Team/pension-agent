import hashlib
from typing import Iterable, List, Optional

from src.models.chunk import ChunkType
from src.models.document import DocumentElement


def make_chunk_id(source_id: str, chunk_type: ChunkType, element_ids: Iterable[str], segment_key: str) -> str:
    payload = "|".join([source_id, chunk_type.value, ",".join(element_ids), segment_key])
    return f"{source_id}-{chunk_type.value}-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]}"


def join_non_empty(parts: Iterable[Optional[str]]) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip()).strip()


def collect_element_ids(elements: Iterable[DocumentElement]) -> List[str]:
    return [element.element_id for element in elements]
