import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.chunk import SearchChunk
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.bm25_retriever import Bm25Retriever
from src.retrieval.tokenizer import SimpleKoreanTokenizer
p=argparse.ArgumentParser();p.add_argument('--query',required=True);p.add_argument('--top-k',type=int,default=5);p.add_argument('--corpus',default='data/parsed/chunks.jsonl');a=p.parse_args()
chunks=[SearchChunk.model_validate_json(x) for x in Path(a.corpus).read_text(encoding='utf-8').splitlines()]
for result in Bm25Retriever(Bm25Index.build(chunks,SimpleKoreanTokenizer())).search(a.query,a.top_k).results:
 print(f"[{result.rank}] score={result.score:.3f}\nsource: {result.source_path}\nlocator: {result.locator.model_dump()}\n{result.text[:1200]}\n")
