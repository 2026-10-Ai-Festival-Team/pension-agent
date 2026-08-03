import json
import pytest
from src.config.generation import GenerationSettings
from src.generation.hcx import HyperClovaXGenerator
from src.generation.errors import GenerationError
from src.models.chunk import ChunkLocator
from src.models.retrieval import SearchResult

class Transport:
    def __init__(self, responses): self.responses=list(responses); self.calls=0
    def post(self,*args): self.calls+=1; return self.responses.pop(0)
def context(): return [SearchResult(rank=1,chunk_id="c1",source_id="s",source_path="x.pdf",source_format="pdf",document_type="p",locator=ChunkLocator(page_start=1,page_end=1),element_ids=["e"],score=1,text="근거")]
def config(retries=0): return GenerationSettings(generator_backend="hcx",hcx_api_key="secret",hcx_model="HCX",hcx_base_url="https://example",max_retries=retries)
def test_parses_json_and_code_fence():
    t=Transport([(200,json.dumps({"choices":[{"message":{"content":"```json\n{\"answer\":\"답변\",\"cited_chunk_ids\":[\"c1\"]}\n```"}}]}))])
    assert HyperClovaXGenerator(config=config(),transport=t).generate(question="q",contexts=context(),query_analysis=None).cited_chunk_ids==["c1"]
def test_auth_is_not_retried():
    t=Transport([(401,"bad")])
    with pytest.raises(GenerationError): HyperClovaXGenerator(config=config(2),transport=t).generate(question="q",contexts=context(),query_analysis=None)
    assert t.calls==1
def test_timeout_like_failure_retries():
    t=Transport([TimeoutError(),(200,json.dumps({"message":{"content":"{\"answer\":\"a\",\"cited_chunk_ids\":[\"c1\"]}"}}))])
    assert HyperClovaXGenerator(config=config(1),transport=t).generate(question="q",contexts=context(),query_analysis=None).answer=="a"
    assert t.calls==2
