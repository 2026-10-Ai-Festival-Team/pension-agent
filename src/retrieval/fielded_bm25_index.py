"""Aligned BM25 field index for table row keys."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.models.chunk import SearchChunk
from src.retrieval.table_row_key_extractor import row_keys


class TableRowKeyIndex:
    def __init__(self, chunks: list[SearchChunk], tokens: list[list[str]], tokenizer) -> None:
        self.chunks, self.tokens, self.tokenizer = chunks, tokens, tokenizer
        # Keep exposed tokens empty for non-table chunks, but give rank_bm25 a
        # private sentinel when every field is empty (it otherwise divides by zero).
        self.bm25 = BM25Okapi([items or ["__no_row_key__"] for items in tokens])

    @classmethod
    def build(cls, chunks: list[SearchChunk], tokenizer):
        return cls(chunks, [tokenizer.tokenize(" ".join(row_keys(chunk))) for chunk in chunks], tokenizer)

    def scores(self, query_tokens: list[str]):
        return self.bm25.get_scores(query_tokens)

    def save(self, path: Path, corpus_path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        with (path / "row_key_tokens.jsonl").open("w", encoding="utf-8") as file:
            for chunk, tokens in zip(self.chunks, self.tokens):
                file.write(json.dumps({"chunk_id": chunk.chunk_id, "tokens": tokens}, ensure_ascii=False) + "\n")
        (path / "index_meta.json").write_text(json.dumps({
            "schema_version": "1.0", "tokenizer": self.tokenizer.name, "chunk_count": len(self.chunks),
            "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
            "bm25": {"algorithm": "BM25Okapi", "k1": 1.5, "b": 0.75}, "field": "table_row_key",
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, chunks: list[SearchChunk], tokenizer, corpus_sha256: str):
        metadata = json.loads((path / "index_meta.json").read_text(encoding="utf-8"))
        if metadata.get("corpus_sha256") != corpus_sha256 or metadata.get("tokenizer") != tokenizer.name or metadata.get("chunk_count") != len(chunks):
            raise RuntimeError("row-key 인덱스가 Corpus·토크나이저와 일치하지 않습니다.")
        rows = [json.loads(line) for line in (path / "row_key_tokens.jsonl").read_text(encoding="utf-8").splitlines() if line]
        if [row["chunk_id"] for row in rows] != [chunk.chunk_id for chunk in chunks]:
            raise RuntimeError("row-key 인덱스의 chunk 순서가 Corpus와 일치하지 않습니다.")
        return cls(chunks, [row["tokens"] for row in rows], tokenizer)
