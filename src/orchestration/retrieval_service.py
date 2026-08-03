"""Construct the frozen Simple BM25 + pension-v1 retrieval dependency."""
from pathlib import Path
from scripts.evaluate_retrieval import load_chunks
from src.evaluation.retrieval_evaluator import load_saved_retriever, sha256_file
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
from src.retrieval.tokenizer import SimpleKoreanTokenizer


class PensionBm25Retriever:
    def __init__(self, retriever) -> None:
        self.retriever = retriever
        self.normalizer = build_default_pension_query_normalizer()

    def search(self, query: str, top_k: int = 5):
        return self.retriever.search(query, top_k=top_k, query_normalizer=self.normalizer)


def build_frozen_retriever(corpus_path: Path, index_path: Path) -> PensionBm25Retriever:
    chunks = load_chunks(corpus_path)
    retriever = load_saved_retriever(index_path, chunks, SimpleKoreanTokenizer(), sha256_file(corpus_path))
    return PensionBm25Retriever(retriever)
