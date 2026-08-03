"""Build the aligned table-row-key index for a stable search Corpus."""
from pathlib import Path
import argparse, sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.evaluate_retrieval import load_chunks
from src.retrieval.fielded_bm25_index import TableRowKeyIndex
from src.retrieval.tokenizer import SimpleKoreanTokenizer

p = argparse.ArgumentParser(); p.add_argument("--corpus", type=Path, default=Path("data/parsed/chunks.jsonl")); p.add_argument("--output", type=Path, required=True)
a = p.parse_args(); chunks = load_chunks(a.corpus); TableRowKeyIndex.build(chunks, SimpleKoreanTokenizer()).save(a.output, a.corpus); print(len(chunks))
