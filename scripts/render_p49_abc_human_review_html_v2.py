"""Render the immutable P48 A/B/C review packet with safe citations.

The A/B/C JSON contains historical model strings and therefore remains
untouched. This view replaces only their presentation ``[근거]`` block through
the same host-owned citation renderer used by runtime.
"""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult
from src.orchestration.citation_renderer import DocumentCitationRenderer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation/fine_tuning/p49_hcx005_abc_p48_regression_v1.json"
RECORDS = ROOT / "evaluation/fine_tuning/p49_draft_gold_training_records_v4.jsonl"
CORPUS = ROOT / "data/parsed/chunks.jsonl"
OUT = ROOT / "evaluation/fine_tuning/p49_hcx005_abc_p48_human_review_v2.html"
IDS = {
    "positive_draft-p48-002", "positive_draft-p48-005", "positive_draft-p48-008",
    "positive_draft-p48-009", "positive_draft-p48-010", "positive_draft-p48-011",
    "positive_draft-p48-014",
}
LANES = {"A_hcx007": "A · HCX-007", "B_hcx005": "B · untuned HCX-005", "C_tuned_hcx005": "C · tuned HCX-005"}
CRITERIA = ["직접 답변", "근거 오독 없음", "필수 사실 완전", "인접 field 없음", "근거 밖 claim 없음", "outcome 행동 적절", "문체·길이 자연스러움"]
# Historical model outputs use both `[chunk_id: …]` and `(chunk_id: …)`.
CHUNK_PATTERN = re.compile(r"[\[(]\s*chunk_id:\s*([^\]\)\s]+)\s*[\]) ]", re.IGNORECASE)


def e(value: object) -> str:
    return html.escape(str(value))


def _load_chunks() -> dict[str, dict]:
    chunks: dict[str, dict] = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunk = json.loads(line)
            chunks[chunk["chunk_id"]] = chunk
    return chunks


def _context(chunk: dict) -> SearchResult:
    return SearchResult(
        rank=1, chunk_id=chunk["chunk_id"], score=1.0, text=chunk["text"],
        source_id=chunk["source_id"], source_path=chunk["source_path"],
        source_format=chunk["source_format"], document_type=chunk["document_type"],
        locator=ChunkLocator(**chunk["locator"]), element_ids=chunk.get("element_ids", []),
        metadata=chunk.get("metadata", {}),
    )


def _replace_citation_block(answer: str, chunks: dict[str, dict], renderer: DocumentCitationRenderer) -> str:
    chunk_ids = CHUNK_PATTERN.findall(answer)
    if not chunk_ids:
        return answer
    missing = [chunk_id for chunk_id in chunk_ids if chunk_id not in chunks]
    if missing:
        raise RuntimeError(f"review answer refers to unknown chunk IDs: {missing}")
    citations = renderer.render(_context(chunks[chunk_id]) for chunk_id in dict.fromkeys(chunk_ids))
    evidence = "[근거]\n" + "\n".join(item.display() for item in citations)
    # Preserve answer body and notices exactly; `[근거]` is presentation-only.
    return re.sub(r"\[근거\].*?(?=\n\s*\[유의사항\]|\Z)", evidence, answer, flags=re.DOTALL)


def main() -> None:
    abc = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = {row["record_id"]: row for row in (json.loads(line) for line in RECORDS.read_text(encoding="utf-8").splitlines() if line.strip())}
    chunks = _load_chunks()
    renderer = DocumentCitationRenderer()
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for result in abc["results"]:
        if result["record_id"] in IDS:
            grouped[result["record_id"]][result["lane"]] = result

    cards: list[str] = []
    for index, record_id in enumerate(sorted(grouped), 1):
        record = records[record_id]
        quality = record["quality"]
        answers = "".join(
            f"<section class='lane'><h3>{LANES[lane]}</h3><pre>{e(_replace_citation_block(grouped[record_id][lane].get('answer', '[provider failure]'), chunks, renderer))}</pre></section>"
            for lane in LANES
        )
        checks = "".join(f"<label><input type='checkbox'> {criterion}</label>" for criterion in CRITERIA)
        cards.append(
            f"<article><h2>{index}. {e(record_id.replace('positive_draft-', '').upper())}</h2>"
            f"<p><b>질문</b> {e(record['question'])}</p>"
            f"<p><b>필수 사실</b> {e(' / '.join(quality.get('required_facts', [])))}</p>"
            f"<p><b>금지 claim</b> {e(' / '.join(quality.get('forbidden_claims', [])))}</p>"
            f"<div class='lanes'>{answers}</div><div class='checks'>{checks}</div>"
            "<p>Overall: <select><option>선택</option><option>PASS</option><option>FAIL</option></select> "
            "Failure: <select><option>none</option><option>omission</option><option>misread</option><option>field_confusion</option><option>unsupported_expansion</option><option>outcome_behavior</option><option>wording</option></select></p>"
            "<textarea placeholder='비교 메모'></textarea></article>"
        )

    OUT.write_text(
        "<!doctype html><meta charset='utf-8'><title>P49 A/B/C Human Review v2</title>"
        "<style>body{font:15px system-ui;max-width:1500px;margin:auto;padding:24px;background:#f6f7fb;color:#172033}article{background:#fff;border:1px solid #dce1ea;border-radius:12px;padding:18px;margin:18px 0}.lanes{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.lane{border:1px solid #dce1ea;border-radius:8px;padding:10px}pre{white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace}.checks{display:flex;flex-wrap:wrap;gap:10px;background:#f4f7fb;padding:10px;border-radius:8px}textarea{width:100%;height:64px}h1{margin-bottom:4px}@media(max-width:900px){.lanes{grid-template-columns:1fr}}</style>"
        "<h1>P49 A/B/C Human Semantic Review</h1>"
        "<p>P48 exposed regression · 7 questions × 3 lanes. [근거] is host-rendered from immutable original outputs; raw runtime IDs are not displayed. Browser inputs are not saved.</p>"
        + "".join(cards), encoding="utf-8"
    )
    print(OUT)


if __name__ == "__main__":
    main()
