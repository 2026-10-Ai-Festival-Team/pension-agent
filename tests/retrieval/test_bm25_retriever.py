from src.models.chunk import SearchChunk,ChunkLocator,ChunkType
from src.retrieval.bm25_index import Bm25Index
from src.retrieval.bm25_retriever import Bm25Retriever
from src.retrieval.tokenizer import SimpleKoreanTokenizer
from src.retrieval.query_normalizer import build_default_pension_query_normalizer
def c(id,text,codes=[]): return SearchChunk(chunk_id=id,source_id=id,source_path=id+'.pdf',source_format='pdf',document_type='investment_product' if codes else 'pension_guide',chunk_type=ChunkType.PARAGRAPH_GROUP,text=text,locator=ChunkLocator(page_start=1,page_end=1),element_ids=[id],product_codes=codes)
def test_retrieval_preserves_evidence_and_code_filter():
 r=Bm25Retriever(Bm25Index.build([c('db','DB형은 회사가 운용합니다.'),c('code','위험등급 5등급',['KR1234567890']),c('tax','연금 수령 과세')],SimpleKoreanTokenizer()))
 assert r.search('DB형 운용').results[0].source_path=='db.pdf'
 assert r.search('KR1234567890').results[0].chunk_id=='code'


def test_retriever_without_normalizer_matches_baseline():
 index=Bm25Index.build([c('transfer','사업자이전 계약이전'),c('other','다른 내용')],SimpleKoreanTokenizer())
 retriever=Bm25Retriever(index)
 query='다른 금융회사로 이전'

 assert index.scores(query).tolist()==index.scores(query,query_normalizer=None).tolist()
 assert retriever.search(query).model_dump()==retriever.search(query,query_normalizer=None).model_dump()


def test_retriever_with_normalizer_keeps_locator():
 chunk=c('transfer','사업자이전 계약이전')
 retriever=Bm25Retriever(Bm25Index.build([chunk,c('other','무관한 문서 내용'),c('other2','별도 안내')],SimpleKoreanTokenizer()))

 result=retriever.search('다른 금융회사로 이전',query_normalizer=build_default_pension_query_normalizer()).results[0]

 assert result.chunk_id==chunk.chunk_id
 assert result.locator==chunk.locator
