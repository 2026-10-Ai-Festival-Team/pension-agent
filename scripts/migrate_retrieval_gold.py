"""Produce manual-review candidates for migrating retrieval gold chunk IDs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_dataset import load_questions
from src.models.chunk import SearchChunk


def overlap_candidate(old_chunk: SearchChunk, new_chunk: SearchChunk) -> dict[str, Any] | None:
    if old_chunk.source_id != new_chunk.source_id:
        return None
    old_ids, new_ids = set(old_chunk.element_ids), set(new_chunk.element_ids)
    overlap = len(old_ids & new_ids)
    if not overlap:
        return None
    return {
        "new_chunk_id": new_chunk.chunk_id,
        "source_id": new_chunk.source_id,
        "element_overlap": overlap,
        "coverage": round(overlap / len(old_ids), 6),
        "precision": round(overlap / len(new_ids), 6),
        "locator": new_chunk.locator.model_dump(mode="json"),
        "element_ids": new_chunk.element_ids,
        "text": new_chunk.text[:500],
    }


def candidates_for_chunk(old_chunk: SearchChunk, new_chunks: list[SearchChunk]) -> list[dict[str, Any]]:
    candidates = [candidate for chunk in new_chunks if (candidate := overlap_candidate(old_chunk, chunk))]
    return sorted(
        candidates,
        key=lambda candidate: (-candidate["element_overlap"], -candidate["coverage"], -candidate["precision"], candidate["new_chunk_id"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--old-corpus", type=Path, required=True)
    parser.add_argument("--new-corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_chunks = {chunk.chunk_id: chunk for chunk in load_chunks(args.old_corpus)}
    new_by_source: dict[str, list[SearchChunk]] = {}
    for chunk in load_chunks(args.new_corpus):
        new_by_source.setdefault(chunk.source_id, []).append(chunk)

    rows: list[dict[str, Any]] = []
    for question in load_questions(args.questions):
        if not question.answerable:
            continue
        for evidence in question.relevant_chunks:
            old_chunk = old_chunks[evidence.chunk_id]
            rows.append(
                {
                    "question_id": question.question_id,
                    "old_chunk_id": old_chunk.chunk_id,
                    "old_source_id": old_chunk.source_id,
                    "old_locator": old_chunk.locator.model_dump(mode="json"),
                    "old_element_ids": old_chunk.element_ids,
                    "relevance": evidence.relevance,
                    "candidates": candidates_for_chunk(old_chunk, new_by_source.get(old_chunk.source_id, [])),
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"gold 후보: {len(rows)}개")
    print(f"출력: {args.output}")


if __name__ == "__main__":
    main()
