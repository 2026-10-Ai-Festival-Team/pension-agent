import hashlib, json
from pathlib import Path
from rank_bm25 import BM25Okapi
from src.models.chunk import SearchChunk
from src.retrieval.document_builder import build_index_text
class Bm25Index:
    def __init__(self,chunks,tokens,tokenizer): self.chunks=chunks; self.tokenized_documents=tokens; self.tokenizer=tokenizer; self.bm25=BM25Okapi(tokens)
    @classmethod
    def build(cls,chunks,tokenizer): return cls(chunks,[tokenizer.tokenize(build_index_text(c)) for c in chunks],tokenizer)
    def scores(self,query): return self.bm25.get_scores(self.tokenizer.tokenize(query))
    def save(self,path,corpus_path):
        path.mkdir(parents=True,exist_ok=True)
        with (path/"tokenized_documents.jsonl").open("w",encoding="utf-8") as f:
            for chunk,tokens in zip(self.chunks,self.tokenized_documents): f.write(json.dumps({"chunk_id":chunk.chunk_id,"tokens":tokens},ensure_ascii=False)+"\n")
        (path/"index_meta.json").write_text(json.dumps({"schema_version":"1.0","tokenizer":self.tokenizer.name,"chunk_count":len(self.chunks),"corpus_path":str(corpus_path),"corpus_sha256":hashlib.sha256(Path(corpus_path).read_bytes()).hexdigest(),"bm25":{"algorithm":"BM25Okapi","k1":1.5,"b":0.75}},ensure_ascii=False,indent=2),encoding="utf-8")
