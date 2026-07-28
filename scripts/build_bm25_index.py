import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.chunk import SearchChunk
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.tokenizer import KiwiKoreanTokenizer,SimpleKoreanTokenizer
p=argparse.ArgumentParser();p.add_argument('--corpus',default='data/parsed/chunks.jsonl');p.add_argument('--output',default='data/indexes/bm25');p.add_argument('--tokenizer',choices=['simple','kiwi'],default='simple');a=p.parse_args()
chunks=[SearchChunk.model_validate_json(x) for x in Path(a.corpus).read_text(encoding='utf-8').splitlines()]; token=SimpleKoreanTokenizer() if a.tokenizer=='simple' else KiwiKoreanTokenizer(); Bm25Index.build(chunks,token).save(Path(a.output),a.corpus);print(len(chunks))
