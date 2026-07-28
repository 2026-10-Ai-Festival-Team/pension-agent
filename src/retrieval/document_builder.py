from src.models.chunk import SearchChunk
def build_index_text(chunk: SearchChunk) -> str:
    return "\n".join(part for part in [chunk.title, chunk.section if chunk.section != chunk.title else None, " ".join(chunk.product_codes), chunk.text] if part)
