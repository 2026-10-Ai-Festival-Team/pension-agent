"""P25-A의 citation 계약 결과를 결정적으로 분류하는 순수 helper."""

from __future__ import annotations


def classify_citation_failure(
    cited_chunk_ids: list[str] | None,
    allowed_chunk_ids: list[str],
    source_ids: list[str],
) -> str | None:
    """자동 보정 없이 원문 ID와 허용 chunk ID를 비교한다."""

    if cited_chunk_ids is None:
        return "missing_citation"
    if not cited_chunk_ids:
        return "empty_citation"
    allowed = set(allowed_chunk_ids)
    if set(cited_chunk_ids).issubset(allowed):
        return None
    if any(value in source_ids for value in cited_chunk_ids):
        return "source_like_identifier"
    if any(
        any(chunk_id.startswith(value) or value.startswith(chunk_id) for chunk_id in allowed)
        for value in cited_chunk_ids
    ):
        return "truncated_chunk_id"
    return "unknown_chunk_id"
