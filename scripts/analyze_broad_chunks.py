"""Diagnose the four normalized dev chunks labeled ``chunk_too_broad``."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_dataset import load_dataset_metadata, load_questions
from src.evaluation.retrieval_evaluator import load_saved_retriever, sha256_file
from src.ingestion.registry import build_default_registry
from src.models.chunk import SearchChunk
from src.models.document import DocumentElement, ElementType
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
from src.retrieval.tokenizer import SimpleKoreanTokenizer


BROAD_QUESTION_IDS = ("R-006", "R-011", "R-019", "R-023")
TOP_K = 10
TOPIC_MARKER = re.compile(r"(?:^|\n)\s*(?:[○■●•]|[①②③④⑤⑥⑦⑧⑨⑩])")


def element_text(element: DocumentElement) -> str:
    if element.table is not None:
        return "\n".join(" | ".join(cell or "" for cell in row).strip() for row in element.table.rows)
    return element.text or ""


def inferred_topic_count(chunk: SearchChunk, elements: list[DocumentElement]) -> int:
    if chunk.chunk_type.value == "table" and elements and elements[0].table is not None:
        return max(1, len(elements[0].table.rows) - 1)
    marker_count = len(TOPIC_MARKER.findall(chunk.text))
    return max(1, marker_count)


def classify_broad_chunk(chunk: SearchChunk, elements: list[DocumentElement]) -> str:
    """Classify A/B using explicit table rows or paragraph topic markers."""
    if inferred_topic_count(chunk, elements) >= 2:
        return "A_mixed_topics"
    return "B_single_topic_long"


def normalized_contains(text: str, term: str) -> bool:
    return re.sub(r"\s+", "", term.lower()) in re.sub(r"\s+", "", text.lower())


def supporting_elements(elements: list[DocumentElement], required_terms: list[str]) -> list[DocumentElement]:
    return [
        element
        for element in elements
        if any(normalized_contains(element_text(element), term) for term in required_terms)
    ]


def context_text(document_elements: list[DocumentElement], selected_ids: set[str], before: bool) -> str:
    positions = [index for index, element in enumerate(document_elements) if element.element_id in selected_ids]
    if not positions:
        return ""
    indexes = range(max(0, min(positions) - 2), min(positions)) if before else range(max(positions) + 1, min(len(document_elements), max(positions) + 3))
    return "\n".join(element_text(document_elements[index]) for index in indexes if element_text(document_elements[index]))[:800]


def result_record(result: Any) -> dict[str, Any]:
    return {
        "rank": result.rank,
        "chunk_id": result.chunk_id,
        "score": round(result.score, 6),
        "char_count": len(result.text),
        "chunk_type": result.metadata.get("chunk_type"),
        "text": result.text[:500],
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, str]]) -> str:
    formats = Counter(row["source_format"] for row in rows)
    types = Counter(row["chunk_type"] for row in rows)
    lines = [
        "# BM25-003: 청크 경계 개선 사전 진단",
        "",
        "## 동기",
        "",
        "`pension-v1` 적용 후 남은 dev 실패에서 `chunk_too_broad`가 4개로 가장 많다. 이 단계에서는 Corpus나 청킹 규칙을 바꾸지 않고, 각 정답 청크가 혼합 주제인지 단일 장문인지 판정한다.",
        "",
        "## 영향 사례",
        "",
        "| ID | 형식 | 청크 유형 | 문자 수 | 토큰 수 | element 수 | 추정 주제 수 | 현재 순위 | 분류 |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {question_id} | {source_format} | {chunk_type} | {char_count} | {token_count} | {element_count} | {topic_count} | {gold_rank} | {classification} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 판정",
            "",
            "네 사례 모두 **A. 여러 주제가 한 청크에 섞인 경우**다. R-006·R-023은 하나의 문단 그룹에 복수의 제도·질문·목록이 결합되어 있고, R-011·R-019는 여러 비교 항목 행을 포함한 표 전체가 하나의 청크다.",
            "",
            "따라서 BM25 길이 정규화 `b` 실험은 진행하지 않는다. 다음 구현 범위는 실제 문제 포맷인 문단 그룹과 표 행 묶음으로 한정한다.",
            "",
            "## 경계 개선 범위",
            "",
            "- 문단: R-006·R-023에서 제목·소제목·목록 경계를 기준으로 분리하고, 제목은 해당 본문 청크에 유지한다.",
            "- 표: R-011·R-019에서 표 제목·헤더를 반복하며 행 묶음을 더 작게 나눈다. 행이나 셀 중간은 자르지 않는다.",
            "- PPTX·XLSX·문제와 무관한 청크 유형은 변경하지 않는다.",
            "",
            "## 근거 추적",
            "",
            "새 Corpus에서는 기존 gold `element_ids`와 새 청크의 교집합으로 이전 후보를 만들고, 38개 답변 가능 질문의 근거 존재·source_id·locator·element_ids를 다시 검증한다. test 질문은 검색 결과를 평가하지 않고 근거 존재 여부만 검증한다.",
            "",
            "상세 element 문맥, Top-10 경쟁 청크, 점수와 질문 필수 용어 일치 비율은 Git 제외 파일 `data/diagnostics/broad_chunk_analysis.csv`에 저장한다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--dataset-meta", type=Path, default=Path("evaluation/retrieval_dataset_meta.json"))
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    parser.add_argument("--simple-index", type=Path, default=Path("data/indexes/bm25/simple"))
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/diagnostics/broad_chunk_analysis.csv"))
    parser.add_argument("--report", type=Path, default=Path("docs/experiments/bm25_003_chunk_boundary.md"))
    args = parser.parse_args()

    load_dotenv()
    source_root = (args.source_root or Path(os.environ["PENSION_DATA_ROOT"])).resolve()
    corpus_sha256 = sha256_file(args.corpus)
    if load_dataset_metadata(args.dataset_meta)["corpus_sha256"] != corpus_sha256:
        raise RuntimeError("평가셋과 현재 Corpus의 SHA-256이 일치하지 않습니다.")
    chunks = load_chunks(args.corpus)
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    tokenizer = SimpleKoreanTokenizer()
    normalizer = build_default_pension_query_normalizer()
    retriever = load_saved_retriever(args.simple_index, chunks, tokenizer, corpus_sha256)
    questions = {question.question_id: question for question in load_questions(args.questions)}
    registry = build_default_registry()
    documents: dict[str, Any] = {}
    rows: list[dict[str, str]] = []

    for question_id in BROAD_QUESTION_IDS:
        question = questions[question_id]
        gold_chunk = chunks_by_id[next(item.chunk_id for item in question.relevant_chunks if item.relevance == 2)]
        document = documents.setdefault(
            gold_chunk.source_id,
            registry.get_parser(source_root / gold_chunk.source_path).parse(source_root / gold_chunk.source_path, source_root),
        )
        element_by_id = {element.element_id: element for element in document.elements}
        gold_elements = [element_by_id[element_id] for element_id in gold_chunk.element_ids]
        supporting = supporting_elements(gold_elements, question.required_terms)
        results = retriever.search(question.question, top_k=TOP_K, query_normalizer=normalizer).results
        current = next((result for result in results if result.chunk_id == gold_chunk.chunk_id), None)
        query_tokens = normalizer.expand(question.question, tokenizer)
        rows.append(
            {
                "question_id": question_id,
                "question": question.question,
                "source_path": gold_chunk.source_path,
                "source_format": gold_chunk.source_format,
                "chunk_type": gold_chunk.chunk_type.value,
                "char_count": str(len(gold_chunk.text)),
                "token_count": str(len(tokenizer.tokenize(gold_chunk.text))),
                "element_count": str(len(gold_chunk.element_ids)),
                "topic_count": str(inferred_topic_count(gold_chunk, gold_elements)),
                "supporting_element_ratio": f"{len(supporting)}/{len(gold_elements)}",
                "gold_rank": str(current.rank if current else ">10"),
                "gold_score": f"{current.score:.6f}" if current else "",
                "classification": classify_broad_chunk(gold_chunk, gold_elements),
                "query_tokens": json.dumps(query_tokens, ensure_ascii=False),
                "gold_element_ids": json.dumps(gold_chunk.element_ids, ensure_ascii=False),
                "previous_elements": context_text(document.elements, set(gold_chunk.element_ids), before=True),
                "next_elements": context_text(document.elements, set(gold_chunk.element_ids), before=False),
                "top10_competitors": json.dumps([result_record(result) for result in results], ensure_ascii=False),
            }
        )
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows), encoding="utf-8")
    print(f"분석 청크: {len(rows)}개")
    print(f"CSV: {args.output}")
    print(f"보고서: {args.report}")


if __name__ == "__main__":
    main()
