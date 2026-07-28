import re
import numpy as np
from src.models.retrieval import SearchResponse, SearchResult
from src.retrieval.bm25_index import Bm25Index
CODE=re.compile(r"KR[A-Z0-9]{10}",re.I)
class Bm25Retriever:
    def __init__(self,index): self.index=index
    def search(self,query,top_k=5,document_types=None,product_codes=None):
        if not query.strip(): raise ValueError("query must not be empty")
        codes={item.upper() for item in CODE.findall(query)}; product_codes={item.upper() for item in (product_codes or set())}|codes
        scores=self.index.scores(query); out=[]
        for idx in np.argsort(scores)[::-1]:
            c=self.index.chunks[int(idx)]
            if scores[int(idx)]<=0: continue
            if document_types and c.document_type not in document_types: continue
            if product_codes and not product_codes.intersection({x.upper() for x in c.product_codes}): continue
            out.append(SearchResult(rank=len(out)+1,chunk_id=c.chunk_id,score=float(scores[int(idx)]),text=c.text,source_id=c.source_id,source_path=c.source_path,source_format=c.source_format,document_type=c.document_type,title=c.title,section=c.section,locator=c.locator,product_codes=c.product_codes,element_ids=c.element_ids,metadata={"retriever":"bm25"}))
            if len(out)>=top_k: break
        return SearchResponse(query=query,tokenizer=self.index.tokenizer.name,total_candidates=len(self.index.chunks),results=out)
