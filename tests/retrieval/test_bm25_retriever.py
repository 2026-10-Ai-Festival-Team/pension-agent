from src.models.chunk import SearchChunk,ChunkLocator,ChunkType
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.bm25_retriever import Bm25Retriever
from src.retrieval.tokenizer import SimpleKoreanTokenizer
def c(id,text,codes=[]): return SearchChunk(chunk_id=id,source_id=id,source_path=id+'.pdf',source_format='pdf',document_type='investment_product' if codes else 'pension_guide',chunk_type=ChunkType.PARAGRAPH_GROUP,text=text,locator=ChunkLocator(page_start=1,page_end=1),element_ids=[id],product_codes=codes)
def test_retrieval_preserves_evidence_and_code_filter():
 r=Bm25Retriever(Bm25Index.build([c('db','DB형은 회사가 운용합니다.'),c('code','위험등급 5등급',['KR1234567890']),c('tax','연금 수령 과세')],SimpleKoreanTokenizer()))
 assert r.search('DB형 운용').results[0].source_path=='db.pdf'
 assert r.search('KR1234567890').results[0].chunk_id=='code'
