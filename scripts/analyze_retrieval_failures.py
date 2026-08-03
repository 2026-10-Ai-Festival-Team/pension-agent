"""Analyze dev-only BM25 retrieval failures without changing retrieval behavior."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_dataset import RetrievalQuestion, load_dataset_metadata, load_questions
from src.evaluation.retrieval_evaluator import load_saved_retriever, sha256_file
from src.models.retrieval import SearchResult
from src.retrieval.query_normalizer import QueryNormalizerProtocol, build_default_pension_query_normalizer
from src.retrieval.tokenizer import KiwiKoreanTokenizer, SearchTokenizer, SimpleKoreanTokenizer


TOP_K = 10

# These labels were assigned from the frozen baseline's dev-only gold and retrieved text.
PRIMARY_FAILURE_LABELS: dict[str, tuple[str, str]] = {
    "R-002": ("evidence_spans_multiple_chunks", "두 페이지의 산정 방식 근거를 함께 찾아야 하는 복합 질의입니다."),
    "R-005": ("query_document_vocabulary_gap", "퇴직금·퇴직연금의 비교 표현이 근거의 제도 설명 표현과 다릅니다."),
    "R-006": ("chunk_too_broad", "정답 본문의 질의 토큰 중첩은 높지만 넓은 제도 안내 청크에 밀립니다."),
    "R-007": ("query_document_vocabulary_gap", "개인부담금·납입 한도 표현이 근거의 문구와 다릅니다."),
    "R-008": ("query_document_vocabulary_gap", "세액공제 한도 질문과 근거의 납입 한도 표현에 어휘 차이가 있습니다."),
    "R-010": ("query_document_vocabulary_gap", "해지 불이익 질문과 연금외수령·기타소득세 근거 사이에 어휘 차이가 있습니다."),
    "R-011": ("chunk_too_broad", "정답 본문의 질의 토큰 중첩은 높지만 직접 근거가 상위 5개 밖에 위치합니다."),
    "R-012": ("query_document_vocabulary_gap", "세액공제 조건이 소득·납입 한도 용어로 분산되어 있습니다."),
    "R-014": ("query_document_vocabulary_gap", "금융회사 이전과 사업자 이전·계약 이전 표현이 다릅니다."),
    "R-015": ("table_rendering", "개인부담금 납입 방법의 직접 근거가 표 요소입니다."),
    "R-017": ("query_document_vocabulary_gap", "승인 없이 가능 여부가 제도 변경·규약 용어와 직접 일치하지 않습니다."),
    "R-018": ("table_rendering", "중도인출 사유의 직접 근거가 표 요소입니다."),
    "R-019": ("chunk_too_broad", "DC 중도인출 조건이 넓은 제도 안내 청크 안에 함께 포함됩니다."),
    "R-020": ("table_rendering", "주택 구입 사유가 중도인출 표의 행으로 나타납니다."),
    "R-022": ("query_document_vocabulary_gap", "일시금·연금 수령 요건 표현이 연금수령 조건 근거와 다릅니다."),
    "R-023": ("chunk_too_broad", "IRP 상품 유형 근거가 넓은 안내 청크 안에 있어 상위 5개 밖에 위치합니다."),
    "R-024": ("repetitive_document_noise", "동일 상품의 표지·목차·반복 표 요소가 직접 근거보다 앞섭니다."),
    "R-026": ("repetitive_document_noise", "동일 상품 문서의 비관련 요소가 환율변동위험 근거보다 앞섭니다."),
    "R-028": ("repetitive_document_noise", "동일 상품 문서의 목차·반복 요소가 투자전략 근거보다 앞섭니다."),
    "R-030": ("table_rendering", "판매수수료·총보수·비용의 직접 근거가 표 요소입니다."),
}


def first_rank(results: list[SearchResult], relevant_ids: set[str]) -> int | None:
    for result in results:
        if result.chunk_id in relevant_ids:
            return result.rank
    return None


def analysis_flags(
    question: RetrievalQuestion,
    simple_rank: int | None,
    kiwi_rank: int | None,
    include_tokenizer_comparison: bool = True,
) -> dict[str, bool]:
    """Return the dev-only conditions that make a question worth failure review."""
    return {
        "simple_direct_top5_failure": simple_rank is None or simple_rank > 5,
        "simple_direct_top10_failure": simple_rank is None,
        "simple_success_kiwi_failure": include_tokenizer_comparison and simple_rank is not None and simple_rank <= 5 and (kiwi_rank is None or kiwi_rank > 5),
        "kiwi_success_simple_failure": include_tokenizer_comparison and kiwi_rank is not None and kiwi_rank <= 5 and (simple_rank is None or simple_rank > 5),
        "all_evidence_question": question.evidence_requirement == "all",
    }


def should_analyze(flags: dict[str, bool]) -> bool:
    return any(flags.values())


def result_record(result: SearchResult) -> dict[str, Any]:
    return {
        "rank": result.rank,
        "chunk_id": result.chunk_id,
        "score": round(result.score, 6),
        "source_id": result.source_id,
        "source_path": result.source_path,
        "locator": result.locator.model_dump(mode="json"),
        "text": result.text,
    }


def make_row(
    question: RetrievalQuestion,
    chunks_by_id: dict[str, Any],
    simple_results: list[SearchResult],
    kiwi_results: list[SearchResult],
    simple_tokenizer: SearchTokenizer,
    kiwi_tokenizer: SearchTokenizer,
    query_normalizer: QueryNormalizerProtocol | None = None,
    include_tokenizer_comparison: bool = True,
) -> dict[str, str]:
    direct_ids = question.direct_evidence_ids
    simple_rank = first_rank(simple_results, direct_ids)
    kiwi_rank = first_rank(kiwi_results, direct_ids)
    flags = analysis_flags(question, simple_rank, kiwi_rank, include_tokenizer_comparison)
    gold_chunks = [chunks_by_id[chunk_id] for chunk_id in sorted(direct_ids)]
    gold_text = "\n\n".join(f"[{chunk.chunk_id}] {chunk.text}" for chunk in gold_chunks)
    gold_titles = "\n".join(chunk.title or "" for chunk in gold_chunks)
    gold_sections = "\n".join(chunk.section or "" for chunk in gold_chunks)
    query_tokens = simple_tokenizer.tokenize(question.question) if query_normalizer is None else query_normalizer.expand(question.question, simple_tokenizer)
    body_tokens = simple_tokenizer.tokenize(gold_text)
    title_tokens = simple_tokenizer.tokenize(gold_titles)
    section_tokens = simple_tokenizer.tokenize(gold_sections)
    title_overlap = sorted(set(query_tokens) & set(title_tokens))
    section_overlap = sorted(set(query_tokens) & set(section_tokens))
    body_overlap = sorted(set(query_tokens) & set(body_tokens))
    failure_type, analysis_note = PRIMARY_FAILURE_LABELS.get(
        question.question_id,
        ("gold_label_issue", "분석 대상 조건에는 해당하지만 사전 원인 라벨이 없습니다."),
    )
    return {
        "question_id": question.question_id,
        "question": question.question,
        "category": question.category,
        "evidence_requirement": question.evidence_requirement,
        "gold_chunk_ids": json.dumps(sorted(direct_ids), ensure_ascii=False),
        "gold_source_ids": json.dumps(sorted({chunk.source_id for chunk in gold_chunks}), ensure_ascii=False),
        "gold_text": gold_text,
        "simple_top10": json.dumps([result_record(result) for result in simple_results], ensure_ascii=False),
        "kiwi_top10": json.dumps([result_record(result) for result in kiwi_results], ensure_ascii=False),
        "simple_query_tokens": json.dumps(query_tokens, ensure_ascii=False),
        "kiwi_query_tokens": json.dumps(kiwi_tokenizer.tokenize(question.question), ensure_ascii=False),
        "simple_gold_tokens": json.dumps(body_tokens, ensure_ascii=False),
        "gold_title_tokens": json.dumps(title_tokens, ensure_ascii=False),
        "gold_section_tokens": json.dumps(section_tokens, ensure_ascii=False),
        "query_title_token_overlap": json.dumps(title_overlap, ensure_ascii=False),
        "query_section_token_overlap": json.dumps(section_overlap, ensure_ascii=False),
        "query_body_token_overlap": json.dumps(body_overlap, ensure_ascii=False),
        "title_section_signal": str(bool(title_overlap or section_overlap) and len(body_overlap) <= 1).lower(),
        "kiwi_gold_tokens": json.dumps(kiwi_tokenizer.tokenize(gold_text), ensure_ascii=False),
        "simple_first_direct_rank": str(simple_rank or ">10"),
        "kiwi_first_direct_rank": str(kiwi_rank or ">10"),
        **{name: str(value).lower() for name, value in flags.items()},
        "failure_type": failure_type,
        "analysis_note": analysis_note,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("분석 대상 dev 질문이 없습니다.")
    with path.open("w", encoding="utf-8-sig", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def render_report(rows: list[dict[str, str]], normalized: bool = False) -> str:
    type_counts: dict[str, list[str]] = {}
    for row in rows:
        type_counts.setdefault(row["failure_type"], []).append(row["question_id"])
    comparison_counts = {
        name: sum(row[name] == "true" for row in rows)
        for name in (
            "simple_direct_top5_failure",
            "simple_direct_top10_failure",
            "simple_success_kiwi_failure",
            "kiwi_success_simple_failure",
            "all_evidence_question",
        )
    }
    lines = [
        "# BM25 검색 실패 분석" + (" (pension-v1 적용)" if normalized else ""),
        "",
        "## 범위",
        "",
        "- 동결 기준선: `v0.5.0-retrieval-baseline`",
        "- 분석 대상: dev 질문만 사용하며 test 질문의 결과·원인 라벨은 포함하지 않는다.",
        "- 검색 로직·토크나이저·청킹은 변경하지 않고, 저장된 Simple 인덱스에서 Top-10을 재현했다.",
        f"- 분석 질문: {len(rows)}개 (선정 조건의 합집합)",
        "",
        "## 선정 조건",
        "",
        "| 조건 | 질문 수 |",
        "|---|---:|",
        f"| Simple 직접 근거 Top-5 실패 | {comparison_counts['simple_direct_top5_failure']} |",
        f"| Simple 직접 근거 Top-10 실패 | {comparison_counts['simple_direct_top10_failure']} |",
        f"| 복합 근거(`all`) | {comparison_counts['all_evidence_question']} |",
        f"| 제목·섹션 신호 후보 | {sum(row['title_section_signal'] == 'true' for row in rows)} |",
        "",
        "## 주원인 분포",
        "",
        "| 주원인 | 질문 |",
        "|---|---|",
    ]
    for failure_type, question_ids in sorted(type_counts.items()):
        lines.append(f"| `{failure_type}` | {', '.join(question_ids)} |")
    lines.extend(
        [
            "",
            "## 관찰",
            "",
            "- 상품코드가 있는 질의는 코드 필터로 동일 상품 문서까지는 좁혀지지만, 표지·목차·반복 표 요소가 직접 근거보다 앞서는 사례가 있다.",
            "- 제도·세제 질문은 사용자의 자연어 표현과 문서의 제도·세무 용어 차이가 주요 원인이다.",
            "- 표의 행에 답이 있는 질문과 복합 근거 질문은 별도 검색 규칙을 추가하기 전에 표 렌더링·인접 근거 확장 후보로 분리한다.",
            "- 제목·섹션 신호 후보가 없으므로 제목·섹션 가중치 실험은 진행하지 않는다. 남은 상위 원인은 청크 범위·표 렌더링·반복 문서 노이즈다." if normalized else "- 제목·섹션 가중치는 정규화 적용 후 별도 진단에서만 검토한다.",
            "",
            "상세 원문·본문·제목·섹션 토큰과 Top-10은 진단 CSV에만 저장한다. 이 파일은 Git에 포함하지 않는다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/retrieval_questions.jsonl"))
    parser.add_argument("--dataset-meta", type=Path, default=Path("evaluation/retrieval_dataset_meta.json"))
    parser.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl"))
    parser.add_argument("--simple-index", type=Path, default=Path("data/indexes/bm25/simple"))
    parser.add_argument("--kiwi-index", type=Path, default=Path("data/indexes/bm25/kiwi"))
    parser.add_argument("--query-normalization", choices=("none", "pension-v1"), default="none")
    parser.add_argument("--output", type=Path, default=Path("data/diagnostics/retrieval_failure_analysis.csv"))
    parser.add_argument("--report", type=Path, default=Path("docs/retrieval_failure_analysis.md"))
    args = parser.parse_args()

    metadata = load_dataset_metadata(args.dataset_meta)
    corpus_sha256 = sha256_file(args.corpus)
    if metadata["corpus_sha256"] != corpus_sha256:
        raise RuntimeError("평가셋과 현재 Corpus의 SHA-256이 일치하지 않습니다.")
    chunks = load_chunks(args.corpus)
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    simple_tokenizer = SimpleKoreanTokenizer()
    simple = load_saved_retriever(args.simple_index, chunks, simple_tokenizer, corpus_sha256)
    normalized = args.query_normalization == "pension-v1"
    query_normalizer = build_default_pension_query_normalizer() if normalized else None
    kiwi_tokenizer = KiwiKoreanTokenizer() if not normalized else simple_tokenizer
    kiwi = load_saved_retriever(args.kiwi_index, chunks, kiwi_tokenizer, corpus_sha256) if not normalized else None

    rows: list[dict[str, str]] = []
    for question in load_questions(args.questions):
        if question.split != "dev" or not question.answerable:
            continue
        simple_results = simple.search(question.question, top_k=TOP_K, query_normalizer=query_normalizer).results
        kiwi_results = kiwi.search(question.question, top_k=TOP_K).results if kiwi else []
        direct_ids = question.direct_evidence_ids
        flags = analysis_flags(
            question,
            first_rank(simple_results, direct_ids),
            first_rank(kiwi_results, direct_ids),
            include_tokenizer_comparison=not normalized,
        )
        if should_analyze(flags):
            rows.append(
                make_row(
                    question,
                    chunks_by_id,
                    simple_results,
                    kiwi_results,
                    simple_tokenizer,
                    kiwi_tokenizer,
                    query_normalizer=query_normalizer,
                    include_tokenizer_comparison=not normalized,
                )
            )
    write_csv(args.output, rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(rows, normalized=normalized), encoding="utf-8")
    print(f"dev 분석 질문 수: {len(rows)}")
    print(f"CSV: {args.output}")
    print(f"보고서: {args.report}")


if __name__ == "__main__":
    main()
