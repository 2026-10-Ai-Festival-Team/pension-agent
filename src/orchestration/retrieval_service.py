"""Construct the frozen Simple BM25 + pension-v1 retrieval dependency."""
from pathlib import Path
import re

from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_evaluator import load_saved_retriever, sha256_file
from src.models.retrieval import SearchResult
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
from src.retrieval.tokenizer import SimpleKoreanTokenizer


class PensionBm25Retriever:
    def __init__(self, retriever) -> None:
        self.retriever = retriever
        self.normalizer = build_default_pension_query_normalizer()

    def search(self, query: str, top_k: int = 5):
        return self.retriever.search(query, top_k=top_k, query_normalizer=self.normalizer)

    def product_field_anchors(self, product_code: str, field: str, top_k: int = 3) -> tuple[SearchResult, ...]:
        """Return direct, product-bound field evidence from the frozen corpus.

        This is deliberately narrower than a second general retrieval pass:
        a candidate must name the requested product *and* directly state the
        requested factual field.  It prevents generic safety text and a
        historical risk-grade log from substituting for a current grade.
        """
        if field not in {"risk_grade", "risk_grade_changeability"} or top_k <= 0:
            return ()
        code = product_code.upper()
        anchors: list[tuple[int, object]] = []
        for chunk in self.retriever.index.chunks:
            if code not in {item.upper() for item in chunk.product_codes}:
                continue
            text = " ".join((chunk.title or "", chunk.section or "", chunk.text))
            compact = " ".join(text.split()).casefold()
            if "위험" not in compact or not re.search(r"[1-6]\s*등급", compact):
                continue
            if field == "risk_grade_changeability":
                if not any(term in compact for term in ("변경될 수", "변경될 가능성", "시장 상황")):
                    continue
                quality = 3
            else:
                # A dated change-history table can prove a past state but not
                # the currently stated grade.  Prefer explicit classification
                # language from the product description.
                quality = 0
                body = " ".join(chunk.text.split()).casefold()
                if re.match(r"투자\s*위험\s*등급\s*[1-6]\s*등급", body):
                    quality += 8
                elif "분류하" in body and re.search(r"[1-6]\s*등급", body):
                    quality += 3
                if "변경내역" in compact or "변경 일" in compact or "변경일" in compact:
                    quality -= 2
                if quality <= 0:
                    continue
            anchors.append((quality, chunk))
        anchors.sort(key=lambda item: (-item[0], item[1].chunk_id))
        return tuple(
            SearchResult(
                rank=position,
                chunk_id=chunk.chunk_id,
                score=float(quality),
                text=chunk.text,
                source_id=chunk.source_id,
                source_path=chunk.source_path,
                source_format=chunk.source_format,
                document_type=chunk.document_type,
                title=chunk.title,
                section=chunk.section,
                locator=chunk.locator,
                source_type=chunk.source_type,
                authority_level=chunk.authority_level,
                as_of_date=chunk.as_of_date,
                product_codes=chunk.product_codes,
                element_ids=chunk.element_ids,
                metadata={"retriever": "product_field_anchor", "field": field},
            )
            for position, (quality, chunk) in enumerate(anchors[:top_k], start=1)
        )


def build_frozen_retriever(corpus_path: Path, index_path: Path) -> PensionBm25Retriever:
    chunks = load_chunks(corpus_path)
    retriever = load_saved_retriever(index_path, chunks, SimpleKoreanTokenizer(), sha256_file(corpus_path))
    return PensionBm25Retriever(retriever)
